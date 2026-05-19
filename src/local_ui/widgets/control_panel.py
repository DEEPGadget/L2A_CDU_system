"""Numeric keypad dialog for PWM duty input.

NumpadDialog: modal popup with configurable min/max range, Apply/Cancel buttons.
Used by CoolingHealthWidget overlay buttons (inline Pump/Fan control).

`min_value` enforces the operational lower bound:
  - Pump: 20 % (= pump_input 17 % Nmin, see PCB.md "유량 추정")
  - Fan:  10 % (운용 권장, spec 무근거)
Values below `min_value` are clamped or rejected on Apply with a hint message.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QVBoxLayout,
)


class NumpadDialog(QDialog):
    """Numeric keypad popup for entering PWM duty (`min_value`–`max_value`)."""

    def __init__(
        self,
        current_value: int,
        parent=None,
        *,
        min_value: int = 0,
        max_value: int = 100,
        title_suffix: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Set PWM Duty (%){title_suffix}")
        self.setModal(True)
        self._min = max(0, int(min_value))
        self._max = min(100, int(max_value))
        if self._min > self._max:
            self._min, self._max = 0, 100
        self._value_str = str(max(self._min, min(self._max, int(current_value))))
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── Display ───────────────────────────────────────────────────────────
        display_font = QFont()
        display_font.setPointSize(28)
        display_font.setBold(True)

        self._display = QLabel(self._value_str)
        self._display.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._display.setFont(display_font)
        self._display.setMinimumHeight(64)
        self._display.setStyleSheet(
            "border:2px solid #bdc3c7; border-radius:6px; padding:6px 12px;"
        )
        layout.addWidget(self._display)

        if self._min > 0 or self._max < 100:
            range_lbl = QLabel(f"입력 범위: {self._min}–{self._max} %")
            range_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            range_lbl.setStyleSheet("color:#6c757d; font-size:10pt;")
            layout.addWidget(range_lbl)

        # ── Numpad grid ───────────────────────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(8)
        btn_font = QFont()
        btn_font.setPointSize(20)

        buttons = [
            ("7", 0, 0), ("8", 0, 1), ("9", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("1", 2, 0), ("2", 2, 1), ("3", 2, 2),
            ("⌫", 3, 0), ("0", 3, 1), ("C", 3, 2),
        ]
        for label, row, col in buttons:
            btn = QPushButton(label)
            btn.setFont(btn_font)
            btn.setMinimumSize(88, 72)
            btn.clicked.connect(lambda _, l=label: self._on_key(l))
            grid.addWidget(btn, row, col)

        layout.addLayout(grid)

        # ── Apply / Cancel ────────────────────────────────────────────────────
        action_font = QFont()
        action_font.setPointSize(16)

        style = self.style()

        apply_btn = QPushButton("Apply")
        apply_btn.setFont(action_font)
        apply_btn.setMinimumHeight(72)
        apply_btn.setIcon(style.standardIcon(QStyle.SP_DialogOkButton))
        apply_btn.setIconSize(QSize(28, 28))
        apply_btn.setLayoutDirection(Qt.RightToLeft)
        apply_btn.setStyleSheet(
            "QPushButton { background:#ffffff; color:#000000; border:2px solid #000000; border-radius:6px; }"
            "QPushButton:pressed { background:#e0e0e0; }"
        )
        apply_btn.clicked.connect(self._on_accept)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFont(action_font)
        cancel_btn.setMinimumHeight(72)
        cancel_btn.setIcon(style.standardIcon(QStyle.SP_DialogCancelButton))
        cancel_btn.setIconSize(QSize(28, 28))
        cancel_btn.setLayoutDirection(Qt.RightToLeft)
        cancel_btn.setStyleSheet(
            "QPushButton { background:#ffffff; color:#000000; border:2px solid #000000; border-radius:6px; }"
            "QPushButton:pressed { background:#e0e0e0; }"
        )
        cancel_btn.clicked.connect(self.reject)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        action_row.addWidget(cancel_btn)
        action_row.addWidget(apply_btn)
        layout.addLayout(action_row)

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
            val = self._min
        if self._min <= val <= self._max:
            self.accept()
        else:
            self._display.setText(f"{self._min}–{self._max} only")
            self._value_str = str(self._min)

    def value(self) -> int:
        try:
            return max(self._min, min(self._max, int(self._value_str)))
        except ValueError:
            return self._min
