"""Settings page — Auto/Manual mode + per-mode detail panels.

Layout (top → bottom):
  ┌─ Mode bar (current mode label + ToggleSwitch reused from top_bar)
  └─ Detail stack (Auto panel / Manual panel)

AutoPanel:
  Fan Curve editor — 4 fields, tap → NumpadDialog (0–100).
  [Save] writes hash `control:fan_curve` + publishes `control:fan_curve:update`.
  Hash duty fields are stored as 0–1000 (=0.0–100.0%); UI shows 0–100%.
  Schema is identical to gadgetini-web settings.js for future D3 sync.

ManualPanel:
  Minimal. Direct pump/fan duty entry is on the Monitoring page overlay.
"""

from __future__ import annotations

import logging

import redis
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.local_ui.widgets.control_panel import NumpadDialog
from src.local_ui.widgets.top_bar import ToggleSwitch

log = logging.getLogger(__name__)

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

_FAN_CURVE_KEY = "control:fan_curve"
_FAN_CURVE_CHANNEL = "control:fan_curve:update"

_DEFAULT_FAN_CURVE = {
    "min_temp": 25,
    "max_temp": 60,
    "min_duty": 100,   # 0–1000 scale → 10%
    "max_duty": 1000,  # 100%
}


def _redis_client() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


class _CurveField(QFrame):
    """Tappable field that opens NumpadDialog and reports the new value."""

    def __init__(self, label: str, suffix: str, value: int, parent=None) -> None:
        super().__init__(parent)
        self._value = value
        self._suffix = suffix
        self._on_change = lambda v: None

        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "QFrame { background:#f8f9fa; border:1px solid #dee2e6; border-radius:8px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        cap_font = QFont(); cap_font.setPointSize(10); cap_font.setBold(True)
        self._caption = QLabel(label.upper())
        self._caption.setFont(cap_font)
        self._caption.setStyleSheet("color:#6c757d; border:none;")

        val_font = QFont(); val_font.setPointSize(22); val_font.setBold(True)
        self._value_lbl = QLabel(self._format(value))
        self._value_lbl.setFont(val_font)
        self._value_lbl.setStyleSheet("color:#212529; border:none;")
        self._value_lbl.setAlignment(Qt.AlignCenter)

        layout.addWidget(self._caption)
        layout.addWidget(self._value_lbl, stretch=1)

        self.setCursor(Qt.PointingHandCursor)

    def _format(self, v: int) -> str:
        return f"{v} {self._suffix}"

    def set_value(self, v: int) -> None:
        self._value = v
        self._value_lbl.setText(self._format(v))

    def value(self) -> int:
        return self._value

    def on_changed(self, callback) -> None:
        self._on_change = callback

    def set_enabled(self, enabled: bool) -> None:
        self.setEnabled(enabled)
        self._value_lbl.setStyleSheet(
            "color:#212529; border:none;" if enabled
            else "color:#adb5bd; border:none;"
        )

    def mousePressEvent(self, event) -> None:
        if not self.isEnabled():
            return
        dlg = NumpadDialog(self._value, parent=self)
        if dlg.exec():
            new_val = dlg.value()
            self.set_value(new_val)
            self._on_change(new_val)


class AutoFanCurvePanel(QWidget):
    """Fan Curve editor — 2-point linear (idle/warning)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._redis = _redis_client()
        self._dirty = False
        self._curve = dict(_DEFAULT_FAN_CURVE)
        self._build_ui()
        self._load_from_redis()

    # ---- UI ----------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        title_font = QFont(); title_font.setPointSize(14); title_font.setBold(True)
        title = QLabel("Fan Curve — Coolant Temp Staging")
        title.setFont(title_font)
        title.setStyleSheet("color:#212529;")

        desc = QLabel(
            "T ≤ Idle Temp → Idle PWM, T ≥ Warning Temp → Max PWM, "
            "사이는 선형 보간 (outlet 온도 기준)."
        )
        desc.setStyleSheet("color:#6c757d; font-size:11pt;")
        desc.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(desc)

        grid = QGridLayout()
        grid.setSpacing(12)

        idle_header = self._group_header("Idle Group", "#27ae60")
        warn_header = self._group_header("Warning Group", "#e74c3c")
        grid.addWidget(idle_header, 0, 0, 1, 2)
        grid.addWidget(warn_header, 0, 2, 1, 2)

        self._f_min_temp = _CurveField("Idle Temp", "°C", self._curve["min_temp"])
        self._f_min_duty = _CurveField("Idle PWM", "%", self._curve["min_duty"] // 10)
        self._f_max_temp = _CurveField("Warning Temp", "°C", self._curve["max_temp"])
        self._f_max_duty = _CurveField("Max PWM", "%", self._curve["max_duty"] // 10)

        grid.addWidget(self._f_min_temp, 1, 0)
        grid.addWidget(self._f_min_duty, 1, 1)
        grid.addWidget(self._f_max_temp, 1, 2)
        grid.addWidget(self._f_max_duty, 1, 3)

        self._f_min_temp.on_changed(lambda v: self._mark_dirty("min_temp", v))
        self._f_min_duty.on_changed(lambda v: self._mark_dirty("min_duty", v * 10))
        self._f_max_temp.on_changed(lambda v: self._mark_dirty("max_temp", v))
        self._f_max_duty.on_changed(lambda v: self._mark_dirty("max_duty", v * 10))

        layout.addLayout(grid)

        # Save bar
        save_row = QHBoxLayout()
        save_row.addStretch(1)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color:#6c757d; font-size:11pt;")
        save_row.addWidget(self._status_lbl)

        self._save_btn = QPushButton("Save")
        self._save_btn.setMinimumSize(140, 56)
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.setStyleSheet(
            "QPushButton { background:#2c3e50; color:white; border:none;"
            " border-radius:8px; font-size:15pt; font-weight:bold; padding:6px 24px; }"
            "QPushButton:disabled { background:#adb5bd; }"
            "QPushButton:pressed { background:#1c2833; }"
        )
        self._save_btn.clicked.connect(self._on_save)
        save_row.addWidget(self._save_btn)

        layout.addStretch(1)
        layout.addLayout(save_row)

        self._refresh_save_state()

    def _group_header(self, text: str, color: str) -> QLabel:
        lbl = QLabel(text)
        font = QFont(); font.setPointSize(11); font.setBold(True)
        lbl.setFont(font)
        lbl.setStyleSheet(f"color:{color}; padding:2px 4px;")
        return lbl

    # ---- State -------------------------------------------------------
    def _mark_dirty(self, field: str, value: int) -> None:
        self._curve[field] = value
        self._dirty = True
        self._refresh_save_state()

    def _refresh_save_state(self) -> None:
        if self._dirty:
            self._save_btn.setEnabled(True)
            self._status_lbl.setText("unsaved changes")
            self._status_lbl.setStyleSheet("color:#e67e22; font-size:11pt;")
        else:
            self._save_btn.setEnabled(False)
            self._status_lbl.setText("saved")
            self._status_lbl.setStyleSheet("color:#27ae60; font-size:11pt;")

    def set_editable(self, editable: bool) -> None:
        for f in (self._f_min_temp, self._f_min_duty,
                  self._f_max_temp, self._f_max_duty):
            f.set_enabled(editable)
        self._save_btn.setEnabled(editable and self._dirty)

    # ---- Redis I/O ---------------------------------------------------
    def _load_from_redis(self) -> None:
        try:
            raw = self._redis.hgetall(_FAN_CURVE_KEY)
        except Exception as e:
            log.warning("control:fan_curve hgetall failed: %s", e)
            raw = {}

        for field in self._curve:
            byte_key = field.encode()
            if byte_key in raw:
                try:
                    self._curve[field] = int(raw[byte_key])
                except ValueError:
                    pass

        self._f_min_temp.set_value(self._curve["min_temp"])
        self._f_max_temp.set_value(self._curve["max_temp"])
        self._f_min_duty.set_value(self._curve["min_duty"] // 10)
        self._f_max_duty.set_value(self._curve["max_duty"] // 10)

        self._dirty = False
        self._refresh_save_state()

    def _on_save(self) -> None:
        try:
            pipe = self._redis.pipeline()
            pipe.hset(_FAN_CURVE_KEY, mapping={
                k: str(v) for k, v in self._curve.items()
            })
            pipe.publish(_FAN_CURVE_CHANNEL, "1")
            pipe.execute()
            log.info("control:fan_curve saved %s", self._curve)
            self._dirty = False
            self._refresh_save_state()
        except Exception as e:
            log.warning("Could not save control:fan_curve: %s", e)
            self._status_lbl.setText(f"save failed: {e}")
            self._status_lbl.setStyleSheet("color:#e74c3c; font-size:11pt;")


class ManualPanel(QWidget):
    """Minimal Manual mode panel."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        title_font = QFont(); title_font.setPointSize(14); title_font.setBold(True)
        title = QLabel("Manual mode")
        title.setFont(title_font)
        title.setStyleSheet("color:#212529;")
        layout.addWidget(title)

        hint = QLabel("펌프/팬 duty 직접 설정은 Monitoring 페이지에서 수행하세요.")
        hint.setStyleSheet("color:#6c757d; font-size:12pt;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addStretch(1)


class SettingsPage(QWidget):
    """Settings page with Auto/Manual toggle and per-mode panels."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._redis = _redis_client()
        self._current_mode = "auto"
        self._build_ui()
        self._sync_mode_from_redis()

    def _build_ui(self) -> None:
        self.setAutoFillBackground(True)
        self.setStyleSheet("SettingsPage { background:#ffffff; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        # ── Mode bar ────────────────────────────────────────────────
        mode_bar = QFrame()
        mode_bar.setStyleSheet(
            "QFrame { background:#f8f9fa; border:1px solid #dee2e6; border-radius:10px; }"
        )
        mode_layout = QHBoxLayout(mode_bar)
        mode_layout.setContentsMargins(16, 12, 16, 12)
        mode_layout.setSpacing(16)

        cap_font = QFont(); cap_font.setPointSize(10); cap_font.setBold(True)
        cap = QLabel("CONTROL MODE")
        cap.setFont(cap_font)
        cap.setStyleSheet("color:#6c757d; border:none;")
        mode_layout.addWidget(cap)

        val_font = QFont(); val_font.setPointSize(16); val_font.setBold(True)
        self._mode_label = QLabel("Auto")
        self._mode_label.setFont(val_font)
        self._mode_label.setStyleSheet("color:#212529; border:none;")
        mode_layout.addWidget(self._mode_label)

        mode_layout.addStretch(1)

        self._mode_switch = ToggleSwitch(checked=True)
        self._mode_switch.toggled.connect(self._on_toggle)
        mode_layout.addWidget(self._mode_switch)

        layout.addWidget(mode_bar)

        # ── Detail stack ────────────────────────────────────────────
        self._stack = QStackedWidget()
        self.auto_panel = AutoFanCurvePanel()
        self.manual_panel = ManualPanel()
        self._stack.addWidget(self.auto_panel)    # index 0
        self._stack.addWidget(self.manual_panel)  # index 1
        layout.addWidget(self._stack, stretch=1)

    # ---- Mode ---------------------------------------------------------
    def _sync_mode_from_redis(self) -> None:
        try:
            raw = self._redis.get("control:mode")
            mode = raw.decode() if isinstance(raw, bytes) else (raw or "auto")
        except Exception:
            mode = "auto"
        self.on_mode_updated(mode)

    def _on_toggle(self, checked: bool) -> None:
        mode = "auto" if checked else "manual"
        try:
            pipe = self._redis.pipeline()
            pipe.set("control:mode", mode)
            pipe.publish("control:mode", mode)
            pipe.execute()
        except Exception as e:
            log.warning("Could not write control:mode: %s", e)

    def on_mode_updated(self, mode: str) -> None:
        """Public slot — wired to RedisSubscriber.mode_updated in main.py."""
        self._current_mode = mode
        if mode == "emergency":
            self._mode_label.setText("Emergency")
            self._mode_label.setStyleSheet("color:#e74c3c; border:none;")
            self._mode_switch.set_emergency(True)
            self._stack.setCurrentIndex(1)
            self.auto_panel.set_editable(False)
        elif mode == "auto":
            self._mode_label.setText("Auto")
            self._mode_label.setStyleSheet("color:#212529; border:none;")
            self._mode_switch.set_emergency(False)
            self._mode_switch.set_checked(True)
            self._stack.setCurrentIndex(0)
            self.auto_panel.set_editable(True)
        else:
            self._mode_label.setText("Manual")
            self._mode_label.setStyleSheet("color:#212529; border:none;")
            self._mode_switch.set_emergency(False)
            self._mode_switch.set_checked(False)
            self._stack.setCurrentIndex(1)
            self.auto_panel.set_editable(False)
