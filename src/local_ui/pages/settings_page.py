"""Settings page — Auto/Manual mode + per-mode detail panels.

Layout (top → bottom):
  ┌─ Mode bar (current mode label + ToggleSwitch reused from top_bar)
  └─ Detail stack
       index 0: AutoControlPanel  — vertical: FanCurveCard + PumpFixedCard
       index 1: ManualPanel       — minimal guidance

AutoControlPanel composes two independent cards:
  • FanCurveCard  — 2-point linear curve (idle/warning), hash `control:fan_curve`
  • PumpFixedCard — single fixed duty (Stage 1),       hash `control:pump_duty`
  Each card has its own Save button. Lower bounds enforced:
    Fan ≥ 10 %, Pump ≥ 20 % (see docs/auto_control.md).

ManualPanel:
  Minimal — direct pump/fan duty entry is on the Monitoring page overlay.
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
_PUMP_DUTY_KEY = "control:pump_duty"
_PUMP_DUTY_CHANNEL = "control:pump_duty:update"

# Operational UI lower bounds (see docs/auto_control.md "L2A UI lower bounds")
PUMP_MIN_UI_DUTY = 20   # %  - pump_input 17% Nmin via 0.85x mapping
FAN_MIN_UI_DUTY  = 10   # %  - operational guideline only (fan spec allows 0-100%)

# Default fan curve (same schema as settings.js; duty is x10 integer in 0-1000)
_DEFAULT_FAN_CURVE = {
    "min_temp": 25,    # C
    "max_temp": 60,    # C
    "min_duty": 100,   # 0-1000 (= 10.0%)
    "max_duty": 1000,  # 0-1000 (= 100.0%)
}
# Default pump fixed duty (Stage 1 policy: 60%, see MCG.md sec 7)
_DEFAULT_PUMP_DUTY = 600   # 0-1000 (= 60.0%)

# Colors
_C_FAN_BG       = "#ecfdf5"   # mint-50 (fan card subtle tint)
_C_PUMP_BG      = "#eff6ff"   # blue-50 (pump card subtle tint)
_C_IDLE_DOT     = "#10b981"   # emerald-500
_C_WARN_DOT     = "#f43f5e"   # rose-500
_C_PUMP_DOT     = "#3b82f6"   # blue-500
_C_SAVE_BG      = "#2563eb"   # blue-600 (deeper accent)
_C_SAVE_PRESS   = "#1d4ed8"
_C_SAVE_DISABLE = "#c7d2fe"
_C_BORDER       = "#e5e7eb"
_C_TEXT         = "#111827"
_C_TEXT_MUTED   = "#4b5563"


def _redis_client() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


class _CurveField(QFrame):
    """Tappable field — opens NumpadDialog with min/max bounds. Hover/pressed states."""

    def __init__(
        self,
        caption: str,
        suffix: str,
        value: int,
        min_value: int,
        max_value: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._value = value
        self._suffix = suffix
        self._caption_txt = caption
        self._min = min_value
        self._max = max_value
        self._on_change = lambda v: None

        # Hover/pressed feedback via stylesheet
        self.setStyleSheet(
            "_CurveField { background:#ffffff; border:1px solid #e5e7eb; border-radius:12px; }"
            "_CurveField:hover { border:1px solid #93c5fd; background:#f9fafb; }"
        )
        self.setAttribute(Qt.WA_Hover, True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(4)

        cap_font = QFont(); cap_font.setPointSize(11); cap_font.setBold(True)
        self._caption = QLabel(caption.upper())
        self._caption.setFont(cap_font)
        self._caption.setStyleSheet(f"color:{_C_TEXT_MUTED}; border:none; letter-spacing:1px;")

        val_font = QFont(); val_font.setPointSize(28); val_font.setBold(True)
        self._value_lbl = QLabel(self._format(value))
        self._value_lbl.setFont(val_font)
        self._value_lbl.setStyleSheet(f"color:{_C_TEXT}; border:none;")

        lay.addWidget(self._caption)
        lay.addWidget(self._value_lbl, stretch=1)
        self.setCursor(Qt.PointingHandCursor)

    def _format(self, v: int) -> str:
        return f"{v}{self._suffix}" if self._suffix else str(v)

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
            f"color:{_C_TEXT}; border:none;" if enabled
            else "color:#9ca3af; border:none;"
        )

    def mousePressEvent(self, event) -> None:
        if not self.isEnabled():
            return
        dlg = NumpadDialog(self._value, parent=self,
                           min_value=self._min, max_value=self._max,
                           title_suffix=f" — {self._caption_txt}")
        if dlg.exec():
            new_val = dlg.value()
            self.set_value(new_val)
            self._on_change(new_val)


class _GroupCard(QFrame):
    """Group card with colored dot + label header + N tappable fields."""

    def __init__(self, title: str, dot_color: str, fields: list[_CurveField],
                 bg: str = "#ffffff", parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"_GroupCard {{ background:{bg}; border:1px solid {_C_BORDER}; border-radius:14px; }}"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(10)
        # Colored dot drawn with QFrame (glyph-free) - some fonts render U+25CF
        # as a missing-glyph box, so we use a CSS-styled QFrame instead.
        dot = QFrame()
        dot.setFixedSize(14, 14)
        dot.setStyleSheet(f"background:{dot_color}; border-radius:7px; border:none;")
        ttl_font = QFont(); ttl_font.setPointSize(13); ttl_font.setBold(True)
        title_lbl = QLabel(title.upper())
        title_lbl.setFont(ttl_font)
        title_lbl.setStyleSheet(f"color:{_C_TEXT}; border:none; letter-spacing:1.5px;")
        header.addWidget(dot, alignment=Qt.AlignVCenter)
        header.addWidget(title_lbl)
        header.addStretch(1)
        outer.addLayout(header)

        grid = QHBoxLayout()
        grid.setSpacing(12)
        for f in fields:
            grid.addWidget(f, stretch=1)
        outer.addLayout(grid)


def _make_save_button() -> QPushButton:
    btn = QPushButton("Save")
    btn.setMinimumSize(140, 50)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background:{_C_SAVE_BG}; color:white; border:none;"
        f" border-radius:10px; font-size:15pt; font-weight:bold; padding:8px 24px; }}"
        f"QPushButton:disabled {{ background:{_C_SAVE_DISABLE}; color:#ffffff; }}"
        f"QPushButton:pressed {{ background:{_C_SAVE_PRESS}; }}"
        f"QPushButton:hover:!disabled {{ background:{_C_SAVE_PRESS}; }}"
    )
    return btn


class FanCurveCard(QWidget):
    """Fan curve editor card (2-point linear: idle / warning)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._redis = _redis_client()
        self._dirty = False
        self._curve = dict(_DEFAULT_FAN_CURVE)
        self._fields: dict[str, _CurveField] = {}
        self._build_ui()
        self._load_from_redis()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background:#ffffff; border:1px solid {_C_BORDER}; border-radius:14px; }}"
        )
        body = QVBoxLayout(card)
        body.setContentsMargins(22, 20, 22, 20)
        body.setSpacing(16)

        title_font = QFont(); title_font.setPointSize(16); title_font.setBold(True)
        title = QLabel("Fan Curve (Auto)")
        title.setFont(title_font)
        title.setStyleSheet(f"color:{_C_TEXT}; border:none;")
        body.addWidget(title)

        desc = QLabel(
            "Below idle temp → idle PWM. Above warning temp → max PWM. "
            "Linear interpolation between."
        )
        desc.setStyleSheet(f"color:{_C_TEXT_MUTED}; font-size:14pt; border:none;")
        desc.setWordWrap(True)
        body.addWidget(desc)

        f_min_temp = _CurveField("Idle Temp", "°C", self._curve["min_temp"], 0, 100)
        f_min_duty = _CurveField("Idle PWM",  "%",  self._curve["min_duty"] // 10,
                                  FAN_MIN_UI_DUTY, 100)
        idle_card = _GroupCard("Idle", _C_IDLE_DOT, [f_min_temp, f_min_duty])

        f_max_temp = _CurveField("Warning Temp", "°C", self._curve["max_temp"], 0, 100)
        f_max_duty = _CurveField("Max PWM",      "%",  self._curve["max_duty"] // 10,
                                  FAN_MIN_UI_DUTY, 100)
        warn_card = _GroupCard("Warning", _C_WARN_DOT, [f_max_temp, f_max_duty])

        self._fields = {
            "min_temp": f_min_temp, "min_duty": f_min_duty,
            "max_temp": f_max_temp, "max_duty": f_max_duty,
        }
        f_min_temp.on_changed(lambda v: self._mark_dirty("min_temp", v))
        f_min_duty.on_changed(lambda v: self._mark_dirty("min_duty", v * 10))
        f_max_temp.on_changed(lambda v: self._mark_dirty("max_temp", v))
        f_max_duty.on_changed(lambda v: self._mark_dirty("max_duty", v * 10))

        groups = QHBoxLayout()
        groups.setSpacing(14)
        groups.addWidget(idle_card, stretch=1)
        groups.addWidget(warn_card, stretch=1)
        body.addLayout(groups)

        save_row = QHBoxLayout()
        save_row.addStretch(1)
        self._save_btn = _make_save_button()
        self._save_btn.clicked.connect(self._on_save)
        save_row.addWidget(self._save_btn)
        body.addLayout(save_row)

        root.addWidget(card)
        self._refresh_save_state()

    # ---- State + I/O ------------------------------------------------
    def _mark_dirty(self, field: str, hash_value: int) -> None:
        self._curve[field] = hash_value
        self._dirty = True
        self._refresh_save_state()

    def _refresh_save_state(self) -> None:
        self._save_btn.setEnabled(self._dirty)

    def set_editable(self, editable: bool) -> None:
        for f in self._fields.values():
            f.set_enabled(editable)
        self._save_btn.setEnabled(editable and self._dirty)

    def _load_from_redis(self) -> None:
        try:
            raw = self._redis.hgetall(_FAN_CURVE_KEY)
        except Exception as e:
            log.warning("control:fan_curve hgetall failed: %s", e)
            raw = {}
        for k in self._curve:
            bk = k.encode()
            if bk in raw:
                try: self._curve[k] = int(raw[bk])
                except ValueError: pass
        self._fields["min_temp"].set_value(self._curve["min_temp"])
        self._fields["max_temp"].set_value(self._curve["max_temp"])
        self._fields["min_duty"].set_value(self._curve["min_duty"] // 10)
        self._fields["max_duty"].set_value(self._curve["max_duty"] // 10)
        self._dirty = False
        self._refresh_save_state()

    def _on_save(self) -> None:
        if self._curve["min_temp"] >= self._curve["max_temp"]:
            log.warning("fan_curve: idle_temp must be < warning_temp"); return
        if self._curve["min_duty"] >= self._curve["max_duty"]:
            log.warning("fan_curve: idle_pwm must be < max_pwm"); return
        try:
            pipe = self._redis.pipeline()
            pipe.hset(_FAN_CURVE_KEY, mapping={k: str(v) for k, v in self._curve.items()})
            pipe.publish(_FAN_CURVE_CHANNEL, "1")
            pipe.execute()
            log.info("control:fan_curve saved %s", self._curve)
            self._dirty = False
            self._refresh_save_state()
        except Exception as e:
            log.warning("Could not save control:fan_curve: %s", e)


class PumpFixedCard(QWidget):
    """Pump fixed-duty editor card (single value, Stage 1 policy)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._redis = _redis_client()
        self._dirty = False
        self._duty = _DEFAULT_PUMP_DUTY  # 0~1000 scale
        self._build_ui()
        self._load_from_redis()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background:#ffffff; border:1px solid {_C_BORDER}; border-radius:14px; }}"
        )
        body = QVBoxLayout(card)
        body.setContentsMargins(22, 20, 22, 20)
        body.setSpacing(16)

        title_font = QFont(); title_font.setPointSize(16); title_font.setBold(True)
        title = QLabel("Pump Fixed Duty (Auto)")
        title.setFont(title_font)
        title.setStyleSheet(f"color:{_C_TEXT}; border:none;")
        body.addWidget(title)

        desc = QLabel(
            f"In Auto mode the pump PWM duty runs at a fixed value. "
            f"Lower bound {PUMP_MIN_UI_DUTY}% (Pump spec 4.2.1 Nmin)."
        )
        desc.setStyleSheet(f"color:{_C_TEXT_MUTED}; font-size:14pt; border:none;")
        desc.setWordWrap(True)
        body.addWidget(desc)

        self._field = _CurveField("Pump Duty", "%",
                                   self._duty // 10,
                                   PUMP_MIN_UI_DUTY, 100)
        self._field.on_changed(lambda v: self._mark_dirty(v * 10))
        group = _GroupCard("Pump", _C_PUMP_DOT, [self._field])
        body.addWidget(group)

        save_row = QHBoxLayout()
        save_row.addStretch(1)
        self._save_btn = _make_save_button()
        self._save_btn.clicked.connect(self._on_save)
        save_row.addWidget(self._save_btn)
        body.addLayout(save_row)

        root.addWidget(card)
        self._refresh_save_state()

    def _mark_dirty(self, hash_value: int) -> None:
        self._duty = hash_value
        self._dirty = True
        self._refresh_save_state()

    def _refresh_save_state(self) -> None:
        self._save_btn.setEnabled(self._dirty)

    def set_editable(self, editable: bool) -> None:
        self._field.set_enabled(editable)
        self._save_btn.setEnabled(editable and self._dirty)

    def _load_from_redis(self) -> None:
        try:
            raw = self._redis.get(_PUMP_DUTY_KEY)
            if raw is not None:
                self._duty = int(raw)
        except Exception as e:
            log.warning("control:pump_duty get failed: %s", e)
        self._field.set_value(self._duty // 10)
        self._dirty = False
        self._refresh_save_state()

    def _on_save(self) -> None:
        try:
            pipe = self._redis.pipeline()
            pipe.set(_PUMP_DUTY_KEY, str(self._duty))
            pipe.publish(_PUMP_DUTY_CHANNEL, str(self._duty))
            pipe.execute()
            log.info("control:pump_duty saved %s", self._duty)
            self._dirty = False
            self._refresh_save_state()
        except Exception as e:
            log.warning("Could not save control:pump_duty: %s", e)


class AutoControlPanel(QWidget):
    """Composite: FanCurveCard + PumpFixedCard side by side (fits 1280×656)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)
        self.fan_card = FanCurveCard()
        self.pump_card = PumpFixedCard()
        # Fan curve has 2 groups (idle/warning) → wider; pump has 1 group → narrower
        layout.addWidget(self.fan_card,  stretch=2)
        layout.addWidget(self.pump_card, stretch=1)

    def set_editable(self, editable: bool) -> None:
        self.fan_card.set_editable(editable)
        self.pump_card.set_editable(editable)


class ManualPanel(QWidget):
    """Minimal Manual-mode panel."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(0)

        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background:#ffffff; border:1px solid {_C_BORDER}; border-radius:14px; }}"
        )
        body = QVBoxLayout(card)
        body.setContentsMargins(22, 20, 22, 20)
        body.setSpacing(12)

        title_font = QFont(); title_font.setPointSize(18); title_font.setBold(True)
        title = QLabel("Manual mode")
        title.setFont(title_font)
        title.setStyleSheet(f"color:{_C_TEXT}; border:none;")
        body.addWidget(title)

        hint = QLabel(
            "Set pump / fan duty directly from the Monitoring page.\n"
            f"Lower bounds: Pump >= {PUMP_MIN_UI_DUTY} %, Fan >= {FAN_MIN_UI_DUTY} %."
        )
        hint.setStyleSheet(f"color:{_C_TEXT_MUTED}; font-size:14pt; border:none;")
        hint.setWordWrap(True)
        body.addWidget(hint)

        outer.addWidget(card)
        outer.addStretch(1)


class SettingsPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._redis = _redis_client()
        self._current_mode = "auto"
        self._build_ui()
        self._sync_mode_from_redis()

    def _build_ui(self) -> None:
        self.setAutoFillBackground(True)
        self.setStyleSheet("SettingsPage { background:#f3f4f6; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Mode bar
        mode_bar = QFrame()
        mode_bar.setStyleSheet(
            f"QFrame {{ background:#ffffff; border:1px solid {_C_BORDER}; border-radius:12px; }}"
        )
        mode_layout = QHBoxLayout(mode_bar)
        mode_layout.setContentsMargins(20, 14, 20, 14)
        mode_layout.setSpacing(18)

        cap_font = QFont(); cap_font.setPointSize(12); cap_font.setBold(True)
        cap = QLabel("CONTROL MODE")
        cap.setFont(cap_font)
        cap.setStyleSheet(f"color:{_C_TEXT_MUTED}; border:none; letter-spacing:2px;")
        mode_layout.addWidget(cap)

        val_font = QFont(); val_font.setPointSize(18); val_font.setBold(True)
        self._mode_label = QLabel("Auto")
        self._mode_label.setFont(val_font)
        self._mode_label.setStyleSheet(f"color:{_C_TEXT}; border:none;")
        mode_layout.addWidget(self._mode_label)

        mode_layout.addStretch(1)

        self._mode_switch = ToggleSwitch(checked=True)
        self._mode_switch.toggled.connect(self._on_toggle)
        mode_layout.addWidget(self._mode_switch)

        layout.addWidget(mode_bar)

        # Detail stack
        self._stack = QStackedWidget()
        self.auto_panel = AutoControlPanel()
        self.manual_panel = ManualPanel()
        self._stack.addWidget(self.auto_panel)
        self._stack.addWidget(self.manual_panel)
        layout.addWidget(self._stack, stretch=1)

    # ---- Mode --------------------------------------------------------
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
        self._current_mode = mode
        if mode == "emergency":
            self._mode_label.setText("Emergency")
            self._mode_label.setStyleSheet("color:#ef4444; border:none;")
            self._mode_switch.set_emergency(True)
            self._stack.setCurrentIndex(1)
            self.auto_panel.set_editable(False)
        elif mode == "auto":
            self._mode_label.setText("Auto")
            self._mode_label.setStyleSheet("color:#111827; border:none;")
            self._mode_switch.set_emergency(False)
            self._mode_switch.set_checked(True)
            self._stack.setCurrentIndex(0)
            self.auto_panel.set_editable(True)
        else:
            self._mode_label.setText("Manual")
            self._mode_label.setStyleSheet("color:#111827; border:none;")
            self._mode_switch.set_emergency(False)
            self._mode_switch.set_checked(False)
            self._stack.setCurrentIndex(1)
            self.auto_panel.set_editable(False)
