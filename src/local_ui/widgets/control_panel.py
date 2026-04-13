"""Control panel widget.

Displays Pump 1/2 and Fan 1/2 PWM duty values (read from Redis sensor:* keys).
Touch on a value → NumpadDialog popup (0–100 range validation).
Apply button → writes changed values directly to Redis (fake mode).

In real mode the Apply button will send commands via IPC to MCG (not yet implemented).
"""

from __future__ import annotations

import logging

import redis
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

log = logging.getLogger(__name__)

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

_DUTY_KEYS = {
    "pump1": "sensor:pump_pwm_duty_1",
    "pump2": "sensor:pump_pwm_duty_2",
    "fan1":  "sensor:fan_pwm_duty_1",
    "fan2":  "sensor:fan_pwm_duty_2",
}

_LABELS = {
    "pump1": "Pump 1 (Loop 1)",
    "pump2": "Pump 2 (Loop 2)",
    "fan1":  "Fan 1 (Loop 1)",
    "fan2":  "Fan 2 (Loop 2)",
}


class NumpadDialog(QDialog):
    """Numeric keypad popup for entering PWM duty (0–100)."""

    def __init__(self, current_value: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set PWM Duty (%)")
        self.setModal(True)
        self._value_str = str(current_value)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        display_font = QFont()
        display_font.setPointSize(24)
        display_font.setBold(True)

        self._display = QLabel(self._value_str)
        self._display.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._display.setFont(display_font)
        self._display.setMinimumHeight(50)
        self._display.setStyleSheet(
            "border:2px solid #bdc3c7; border-radius:6px; padding:4px 8px;"
        )
        layout.addWidget(self._display)

        grid = QGridLayout()
        grid.setSpacing(6)
        btn_font = QFont()
        btn_font.setPointSize(18)

        buttons = [
            ("7", 0, 0), ("8", 0, 1), ("9", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("1", 2, 0), ("2", 2, 1), ("3", 2, 2),
            ("⌫", 3, 0), ("0", 3, 1), ("C", 3, 2),
        ]
        for label, row, col in buttons:
            btn = QPushButton(label)
            btn.setFont(btn_font)
            btn.setMinimumSize(70, 60)
            btn.clicked.connect(lambda _, l=label: self._on_key(l))
            grid.addWidget(btn, row, col)

        layout.addLayout(grid)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_key(self, label: str) -> None:
        if label == "⌫":
            self._value_str = self._value_str[:-1] or "0"
        elif label == "C":
            self._value_str = "0"
        else:
            if self._value_str == "0":
                self._value_str = label
            else:
                self._value_str += label
        self._display.setText(self._value_str)

    def _on_accept(self) -> None:
        try:
            val = int(self._value_str)
        except ValueError:
            val = 0
        if 0 <= val <= 100:
            self.accept()
        else:
            self._display.setText("0–100 only")
            self._value_str = "50"

    def value(self) -> int:
        try:
            return max(0, min(100, int(self._value_str)))
        except ValueError:
            return 0


class ControlPanelWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
        self._current: dict[str, int] = {k: 0 for k in _DUTY_KEYS}
        self._pending: dict[str, int] = {}
        self._value_labels: dict[str, QLabel] = {}
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)

        title = QLabel("Control")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title.setFont(title_font)
        outer.addWidget(title)

        group = QGroupBox()
        grid = QGridLayout(group)
        grid.setSpacing(8)

        row_font = QFont()
        row_font.setPointSize(12)

        for row_idx, (slot, display_label) in enumerate(_LABELS.items()):
            name_lbl = QLabel(display_label)
            name_lbl.setFont(row_font)

            val_lbl = QLabel("-- %")
            val_lbl.setFont(row_font)
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val_lbl.setMinimumWidth(60)
            self._value_labels[slot] = val_lbl

            edit_btn = QPushButton("Edit")
            edit_btn.setFont(row_font)
            edit_btn.setFixedWidth(60)
            edit_btn.clicked.connect(lambda _, s=slot: self._on_edit(s))

            grid.addWidget(name_lbl, row_idx, 0)
            grid.addWidget(val_lbl,  row_idx, 1)
            grid.addWidget(edit_btn, row_idx, 2)

        outer.addWidget(group)

        # Leak status
        leak_layout = QHBoxLayout()
        leak_name = QLabel("Leak")
        leak_name.setFont(row_font)
        self._leak_label = QLabel("None")
        self._leak_label.setFont(row_font)
        self._leak_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        leak_layout.addWidget(leak_name)
        leak_layout.addWidget(self._leak_label)
        outer.addLayout(leak_layout)

        # Apply button
        self._apply_btn = QPushButton("Apply")
        apply_font = QFont()
        apply_font.setPointSize(14)
        apply_font.setBold(True)
        self._apply_btn.setFont(apply_font)
        self._apply_btn.setMinimumHeight(48)
        self._apply_btn.setStyleSheet(
            "background:#2980b9; color:white; border-radius:8px;"
        )
        self._apply_btn.clicked.connect(self._on_apply)
        outer.addWidget(self._apply_btn)

        outer.addStretch()

    # ------------------------------------------------------------------
    # Signal handlers

    def on_sensor_updated(self, key: str, value: str) -> None:
        for slot, redis_key in _DUTY_KEYS.items():
            if key == redis_key:
                try:
                    val = int(float(value))
                except ValueError:
                    val = 0
                self._current[slot] = val
                # Only refresh display if no pending edit for this slot
                if slot not in self._pending:
                    self._value_labels[slot].setText(f"{val} %")
                return

        if key == "sensor:leak":
            self._leak_label.setText("Detected" if value == "LEAKED" else "None")
            color = "#e74c3c" if value == "LEAKED" else "#27ae60"
            self._leak_label.setStyleSheet(f"color:{color};")

    # ------------------------------------------------------------------
    # Edit / Apply

    def _on_edit(self, slot: str) -> None:
        current = self._pending.get(slot, self._current[slot])
        dlg = NumpadDialog(current, parent=self)
        if dlg.exec() == QDialog.Accepted:
            new_val = dlg.value()
            self._pending[slot] = new_val
            self._value_labels[slot].setText(f"{new_val} % *")

    def _on_apply(self) -> None:
        if not self._pending:
            return
        pipe = self._redis.pipeline()
        for slot, new_val in self._pending.items():
            redis_key = _DUTY_KEYS[slot]
            pipe.set(redis_key, str(new_val))
            pipe.publish(redis_key, str(new_val))
            self._current[slot] = new_val
            self._value_labels[slot].setText(f"{new_val} %")
            log.info("Applied %s = %d%%", redis_key, new_val)
        pipe.execute()
        self._pending.clear()
