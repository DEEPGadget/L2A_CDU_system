"""Numeric keypad dialog for PWM duty input.

NumpadDialog: modal popup with configurable min/max range, Apply/Cancel buttons.
Used by CoolingHealthWidget overlay buttons and Settings page tappable fields.

`min_value` enforces the operational lower bound:
  - Pump: 20 % (= pump_input 17 % Nmin, see PCB.md "Flow estimation")
  - Fan:  10 % (operational guideline only, not from spec)
Values below `min_value` are clamped or rejected on Apply.

Design:
  - Frameless dialog (no OS chrome) — fully controlled appearance.
  - White card wrapped in 2 px black border, centered on the primary screen.
  - ASCII-only labels (back/Apply/Cancel). Avoids glyph fallback issues on
    Raspberry Pi default fonts (no ✓, ⌫, ⚠, ● — those rendered as boxes).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

# ── Color palette ─────────────────────────────────────────────────────────────
_C_BG          = "#ffffff"
_C_BORDER      = "#000000"          # solid black border (per requirement)
_C_TEXT        = "#111827"
_C_TEXT_MUTED  = "#6b7280"
_C_HINT        = "#9ca3af"
_C_DISPLAY_BG  = "#f9fafb"
_C_NUM_BG      = "#ffffff"
_C_NUM_BORDER  = "#d1d5db"
_C_NUM_HOVER   = "#f3f4f6"
_C_NUM_PRESS   = "#e5e7eb"
_C_AUX_BG      = "#f9fafb"
_C_AUX_TEXT    = "#6b7280"
_C_APPLY_BG    = "#2563eb"          # blue-600
_C_APPLY_PRESS = "#1d4ed8"
_C_CANCEL_BG   = "#ffffff"
_C_CANCEL_TEXT = "#374151"

_NUMPAD_BTN_STYLE = (
    f"QPushButton {{ background:{_C_NUM_BG}; color:{_C_TEXT}; border:1px solid {_C_NUM_BORDER};"
    f" border-radius:10px; font-size:22pt; font-weight:600; }}"
    f"QPushButton:hover {{ background:{_C_NUM_HOVER}; border:1px solid #93c5fd; }}"
    f"QPushButton:pressed {{ background:{_C_NUM_PRESS}; }}"
)
_AUX_BTN_STYLE = (
    f"QPushButton {{ background:{_C_AUX_BG}; color:{_C_AUX_TEXT}; border:1px solid {_C_NUM_BORDER};"
    f" border-radius:10px; font-size:18pt; font-weight:600; }}"
    f"QPushButton:hover {{ background:{_C_NUM_HOVER}; border:1px solid #93c5fd; }}"
    f"QPushButton:pressed {{ background:{_C_NUM_PRESS}; }}"
)
_APPLY_BTN_STYLE = (
    f"QPushButton {{ background:{_C_APPLY_BG}; color:white; border:none;"
    f" border-radius:10px; font-size:16pt; font-weight:bold; padding:0 24px; }}"
    f"QPushButton:hover {{ background:{_C_APPLY_PRESS}; }}"
    f"QPushButton:pressed {{ background:{_C_APPLY_PRESS}; }}"
)
_CANCEL_BTN_STYLE = (
    f"QPushButton {{ background:{_C_CANCEL_BG}; color:{_C_CANCEL_TEXT}; border:1px solid #d1d5db;"
    f" border-radius:10px; font-size:16pt; font-weight:600; padding:0 24px; }}"
    f"QPushButton:hover {{ background:{_C_NUM_HOVER}; }}"
    f"QPushButton:pressed {{ background:{_C_NUM_PRESS}; }}"
)


class NumpadDialog(QDialog):
    """Numeric keypad popup (`min_value`–`max_value`). Frameless + centered."""

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
        self.setModal(True)
        # Frameless: strip OS chrome, use our own black-border card.
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self._min = max(0, int(min_value))
        self._max = min(100, int(max_value))
        if self._min > self._max:
            self._min, self._max = 0, 100
        self._title_suffix = title_suffix.strip(" -—") or "Set Duty"
        self._value_str = str(max(self._min, min(self._max, int(current_value))))
        self._build_ui()

    def _build_ui(self) -> None:
        # ── Outer wrapper (transparent) ──────────────────────────────────────
        # Frameless dialog; the inner card is the visible surface.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("dialogCard")
        card.setStyleSheet(
            f"QFrame#dialogCard {{ background:{_C_BG}; border:2px solid {_C_BORDER};"
            f" border-radius:14px; }}"
        )
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 22, 22, 22)

        # ── Title row ────────────────────────────────────────────────────────
        title_lbl = QLabel(self._title_suffix)
        tf = QFont(); tf.setPointSize(13); tf.setBold(True)
        title_lbl.setFont(tf)
        title_lbl.setStyleSheet(f"color:{_C_TEXT_MUTED}; border:none; letter-spacing:1px;")
        layout.addWidget(title_lbl)

        # ── Display ───────────────────────────────────────────────────────────
        display_card = QLabel()
        display_card.setObjectName("displayCard")
        df = QFont(); df.setPointSize(36); df.setBold(True)
        display_card.setFont(df)
        display_card.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        display_card.setMinimumHeight(96)
        display_card.setStyleSheet(
            f"QLabel#displayCard {{ background:{_C_DISPLAY_BG}; color:{_C_TEXT};"
            f" border:1px solid #d1d5db; border-radius:12px;"
            f" padding:10px 22px; }}"
        )
        display_card.setText(f"{self._value_str} %")
        self._display = display_card
        layout.addWidget(display_card)

        range_lbl = QLabel(f"Allowed range: {self._min} - {self._max} %")
        range_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        range_lbl.setStyleSheet(f"color:{_C_HINT}; font-size:12pt; border:none;")
        layout.addWidget(range_lbl)
        self._range_lbl = range_lbl

        # ── Numpad grid ──────────────────────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(8)
        # ASCII-only labels (avoid arrow/glyph fallback boxes).
        digit_buttons = [
            ("7",    0, 0), ("8", 0, 1), ("9", 0, 2),
            ("4",    1, 0), ("5", 1, 1), ("6", 1, 2),
            ("1",    2, 0), ("2", 2, 1), ("3", 2, 2),
            ("Back", 3, 0), ("0", 3, 1), ("C", 3, 2),
        ]
        for label, row, col in digit_buttons:
            btn = QPushButton(label)
            btn.setMinimumSize(96, 76)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(_AUX_BTN_STYLE if label in ("Back", "C") else _NUMPAD_BTN_STYLE)
            btn.clicked.connect(lambda _, l=label: self._on_key(l))
            grid.addWidget(btn, row, col)
        layout.addLayout(grid)

        # ── Apply / Cancel ───────────────────────────────────────────────────
        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(56)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(_CANCEL_BTN_STYLE)
        cancel_btn.clicked.connect(self.reject)

        apply_btn = QPushButton("Apply")
        apply_btn.setMinimumHeight(56)
        apply_btn.setCursor(Qt.PointingHandCursor)
        apply_btn.setStyleSheet(_APPLY_BTN_STYLE)
        apply_btn.clicked.connect(self._on_accept)

        action_row.addWidget(cancel_btn, stretch=1)
        action_row.addWidget(apply_btn,  stretch=2)
        layout.addLayout(action_row)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Center on primary screen (kiosk env - do not depend on parent position)
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            dlg_geo = self.frameGeometry()
            dlg_geo.moveCenter(geo.center())
            self.move(dlg_geo.topLeft())

    def _on_key(self, label: str) -> None:
        if label == "Back":
            self._value_str = self._value_str[:-1] or "0"
        elif label == "C":
            self._value_str = "0"
        else:
            if self._value_str == "0":
                self._value_str = label
            else:
                if len(self._value_str) >= 3:
                    return  # block more than 3 digits (max 100)
                self._value_str += label
        self._display.setText(f"{self._value_str} %")

    def _on_accept(self) -> None:
        try:
            val = int(self._value_str)
        except ValueError:
            val = self._min
        if self._min <= val <= self._max:
            self.accept()
        else:
            self._range_lbl.setText(
                f"Only {self._min} - {self._max} % allowed"
            )
            self._range_lbl.setStyleSheet(
                "color:#ef4444; font-size:12pt; font-weight:bold; border:none;"
            )
            self._value_str = str(self._min)
            self._display.setText(f"{self._value_str} %")

    def value(self) -> int:
        try:
            return max(self._min, min(self._max, int(self._value_str)))
        except ValueError:
            return self._min
