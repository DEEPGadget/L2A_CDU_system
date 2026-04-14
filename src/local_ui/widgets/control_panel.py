"""Numeric keypad dialog for PWM duty input.

NumpadDialog: modal popup, 0–100 range, Apply/Cancel buttons.
Used by CoolingHealthWidget overlay buttons (inline Pump/Fan control).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


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
        btn_box.button(QDialogButtonBox.Ok).setText("Apply")
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
