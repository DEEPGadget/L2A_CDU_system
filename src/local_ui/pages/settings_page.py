"""Settings page — Auto/Manual mode + per-mode detail panels.

Layout (top → bottom):
  ┌─ Mode bar (current mode label + ToggleSwitch reused from top_bar)
  └─ Detail stack (Auto PI panel / Manual minimal panel)

AutoPIPanel (Stage 2 PI per docs/auto_control.md):
  Fan group: setpoint, base_duty, Kp, Ki, out_min, out_max
  Pump group: pump.duty (Stage 1 고정 duty; Stage 3 PI 진입 전까지)
  [Save] writes hash `control:auto` + publishes `control:auto:update`.

  Hash schema (all integers — UI uses NumpadDialog 0–99/0–100):
    fan.setpoint   °C            (e.g. 40)
    fan.base_duty  0–1000 (×10)  (e.g. 400 = 40.0%)
    fan.kp         integer       (e.g. 5  — meaning Kp 5.0 %P/°C)
    fan.ki         integer       (e.g. 1  — meaning Ki 1.0 %P/(°C·s))
    fan.out_min    0–1000 (×10)  (e.g. 100 = 10.0% — FAN_MIN_UI_DUTY)
    fan.out_max    0–1000 (×10)  (e.g. 1000 = 100.0%)
    pump.duty      0–1000 (×10)  (e.g. 600 = 60.0%, ≥ 200 = ≥20% pump UI lower)

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

_AUTO_HASH_KEY = "control:auto"
_AUTO_UPDATE_CHANNEL = "control:auto:update"

# Operational lower bounds (mirror cooling_health.py)
PUMP_MIN_UI_DUTY = 20   # %  — pump_input 17% Nmin via 0.85× mapping
FAN_MIN_UI_DUTY  = 10   # %  — operational guideline (fan spec 0~100% 전 구간)

# Default auto params (per docs/auto_control.md Stage 2)
_DEFAULT_AUTO = {
    "fan.setpoint":   40,    # °C
    "fan.base_duty":  400,   # ×10 = 40.0%
    "fan.kp":         5,     # ≈ 5.0 %P/°C
    "fan.ki":         1,     # ≈ 1.0 %P/(°C·s)  (auto_control.md 0.5 → 정수 근사)
    "fan.out_min":    FAN_MIN_UI_DUTY * 10,    # 100 = 10.0%
    "fan.out_max":    1000,  # 100.0%
    "pump.duty":      600,   # 60.0% (Stage 1 고정)
}


def _redis_client() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


class _ParamField(QFrame):
    """Tappable parameter card — opens NumpadDialog and reports the new value."""

    def __init__(
        self,
        label: str,
        suffix: str,
        value: int,
        min_value: int = 0,
        max_value: int = 100,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._value = value
        self._suffix = suffix
        self._label = label
        self._min = min_value
        self._max = max_value
        self._on_change = lambda v: None

        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "QFrame { background:#f8f9fa; border:1px solid #dee2e6; border-radius:8px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        cap_font = QFont(); cap_font.setPointSize(9); cap_font.setBold(True)
        self._caption = QLabel(label.upper())
        self._caption.setFont(cap_font)
        self._caption.setStyleSheet("color:#6c757d; border:none;")
        self._caption.setWordWrap(True)

        val_font = QFont(); val_font.setPointSize(20); val_font.setBold(True)
        self._value_lbl = QLabel(self._format(value))
        self._value_lbl.setFont(val_font)
        self._value_lbl.setStyleSheet("color:#212529; border:none;")
        self._value_lbl.setAlignment(Qt.AlignCenter)

        layout.addWidget(self._caption)
        layout.addWidget(self._value_lbl, stretch=1)

        self.setCursor(Qt.PointingHandCursor)

    def _format(self, v: int) -> str:
        return f"{v} {self._suffix}" if self._suffix else str(v)

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
        dlg = NumpadDialog(self._value, parent=self,
                           min_value=self._min, max_value=self._max,
                           title_suffix=f" — {self._label}")
        if dlg.exec():
            new_val = dlg.value()
            self.set_value(new_val)
            self._on_change(new_val)


class AutoPIPanel(QWidget):
    """Stage 2 PI parameter editor (fan) + Stage 1 fixed pump duty.

    See docs/auto_control.md "Stage 2" for the PI equation:
        error    = outlet_temp - setpoint
        fan_pwm  = clamp(base_duty + Kp*error + Ki*∫error, out_min, out_max)
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._redis = _redis_client()
        self._dirty = False
        self._params = dict(_DEFAULT_AUTO)
        self._fields: dict[str, _ParamField] = {}
        self._build_ui()
        self._load_from_redis()

    # ---- UI ----------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        title_font = QFont(); title_font.setPointSize(14); title_font.setBold(True)
        title = QLabel("Auto Control — Fan PI + Pump fixed")
        title.setFont(title_font)
        title.setStyleSheet("color:#212529;")

        desc = QLabel(
            "Fan: outlet 온도 setpoint 기준 PI 제어 "
            "(auto_control.md Stage 2). "
            "Pump: 고정 duty (Stage 1). "
            f"하한 Fan ≥ {FAN_MIN_UI_DUTY}% · Pump ≥ {PUMP_MIN_UI_DUTY}%."
        )
        desc.setStyleSheet("color:#6c757d; font-size:11pt;")
        desc.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(desc)

        # ── Fan PI group ─────────────────────────────────────────────
        layout.addWidget(self._group_header("Fan PI", "#3498db"))

        fan_grid = QGridLayout()
        fan_grid.setSpacing(10)

        # NOTE: Kp/Ki 는 정수 의미 그대로 (5 = Kp 5.0, 1 = Ki 1.0). 소수 입력 필요 시
        # 추후 dedicated dialog 추가.
        specs = [
            # (hash_key,        label,         suffix,  min,             max, scale_to_ui)
            ("fan.setpoint",    "Setpoint",    "°C",    20,              80,  lambda v: v),
            ("fan.base_duty",   "Base Duty",   "%",     FAN_MIN_UI_DUTY, 100, lambda v: v // 10),
            ("fan.kp",          "Kp",          "",      0,               99,  lambda v: v),
            ("fan.ki",          "Ki",          "",      0,               99,  lambda v: v),
            ("fan.out_min",     "Out Min",     "%",     FAN_MIN_UI_DUTY, 100, lambda v: v // 10),
            ("fan.out_max",     "Out Max",     "%",     FAN_MIN_UI_DUTY, 100, lambda v: v // 10),
        ]
        for col, (key, label, sfx, mn, mx, to_ui) in enumerate(specs):
            field = _ParamField(label, sfx, to_ui(self._params[key]),
                                 min_value=mn, max_value=mx)
            row = col // 3
            col2 = col % 3
            fan_grid.addWidget(field, row, col2)
            self._fields[key] = field

        # Bind change handlers (convert UI value → hash value)
        self._fields["fan.setpoint"].on_changed(lambda v: self._mark_dirty("fan.setpoint", v))
        self._fields["fan.base_duty"].on_changed(lambda v: self._mark_dirty("fan.base_duty", v * 10))
        self._fields["fan.kp"].on_changed(lambda v: self._mark_dirty("fan.kp", v))
        self._fields["fan.ki"].on_changed(lambda v: self._mark_dirty("fan.ki", v))
        self._fields["fan.out_min"].on_changed(lambda v: self._mark_dirty("fan.out_min", v * 10))
        self._fields["fan.out_max"].on_changed(lambda v: self._mark_dirty("fan.out_max", v * 10))

        layout.addLayout(fan_grid)

        # ── Pump fixed group ─────────────────────────────────────────
        layout.addWidget(self._group_header("Pump (fixed duty)", "#27ae60"))

        pump_row = QHBoxLayout()
        pump_field = _ParamField("Pump Duty", "%",
                                  self._params["pump.duty"] // 10,
                                  min_value=PUMP_MIN_UI_DUTY, max_value=100)
        pump_field.on_changed(lambda v: self._mark_dirty("pump.duty", v * 10))
        self._fields["pump.duty"] = pump_field
        pump_row.addWidget(pump_field)
        pump_row.addStretch(1)
        layout.addLayout(pump_row)

        # ── Save bar ─────────────────────────────────────────────────
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
    def _mark_dirty(self, hash_key: str, hash_value: int) -> None:
        self._params[hash_key] = hash_value
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
        for f in self._fields.values():
            f.set_enabled(editable)
        self._save_btn.setEnabled(editable and self._dirty)

    # ---- Redis I/O ---------------------------------------------------
    def _load_from_redis(self) -> None:
        try:
            raw = self._redis.hgetall(_AUTO_HASH_KEY)
        except Exception as e:
            log.warning("control:auto hgetall failed: %s", e)
            raw = {}

        for key in self._params:
            byte_key = key.encode()
            if byte_key in raw:
                try:
                    self._params[key] = int(raw[byte_key])
                except ValueError:
                    pass

        # Repopulate UI (apply scale)
        self._fields["fan.setpoint"].set_value(self._params["fan.setpoint"])
        self._fields["fan.base_duty"].set_value(self._params["fan.base_duty"] // 10)
        self._fields["fan.kp"].set_value(self._params["fan.kp"])
        self._fields["fan.ki"].set_value(self._params["fan.ki"])
        self._fields["fan.out_min"].set_value(self._params["fan.out_min"] // 10)
        self._fields["fan.out_max"].set_value(self._params["fan.out_max"] // 10)
        self._fields["pump.duty"].set_value(self._params["pump.duty"] // 10)

        self._dirty = False
        self._refresh_save_state()

    def _on_save(self) -> None:
        # Cross-field guard: out_min < out_max
        if self._params["fan.out_min"] >= self._params["fan.out_max"]:
            self._status_lbl.setText("out_min must be < out_max")
            self._status_lbl.setStyleSheet("color:#e74c3c; font-size:11pt;")
            return
        try:
            pipe = self._redis.pipeline()
            pipe.hset(_AUTO_HASH_KEY, mapping={
                k: str(v) for k, v in self._params.items()
            })
            pipe.publish(_AUTO_UPDATE_CHANNEL, "1")
            pipe.execute()
            log.info("control:auto saved %s", self._params)
            self._dirty = False
            self._refresh_save_state()
        except Exception as e:
            log.warning("Could not save control:auto: %s", e)
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

        hint = QLabel(
            "펌프/팬 duty 직접 설정은 Monitoring 페이지에서 수행하세요. "
            f"입력 하한: Pump ≥ {PUMP_MIN_UI_DUTY}%, Fan ≥ {FAN_MIN_UI_DUTY}%."
        )
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
        self.auto_panel = AutoPIPanel()
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
