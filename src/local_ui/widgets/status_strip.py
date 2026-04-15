"""Status strip widget — fixed bottom bar.

Displays: ΔT1, ΔT2, Leak, Ambient Temp/Humidity, Pressure.
Placed below the Cooling Health SVG as a separate QWidget.
Updated via on_sensor_updated() signal from main window.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

_C_NORMAL   = "#27ae60"
_C_WARNING  = "#e67e22"
_C_CRITICAL = "#e74c3c"
_C_BLACK    = "#000000"

_STRIP_HEIGHT = 76



class StatusStripWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._inlet1  = "--"
        self._inlet2  = "--"
        self._outlet1 = "--"
        self._outlet2 = "--"
        self._amb_temp = "--"
        self._amb_hum  = "--"
        self._build_ui()

    def _build_ui(self) -> None:
        self.setFixedHeight(_STRIP_HEIGHT)
        self.setStyleSheet("background:#ffffff; border-top:1px solid #dee2e6;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(0)

        lbl_font = QFont()
        lbl_font.setPointSize(15)

        val_font = QFont()
        val_font.setPointSize(15)

        def add_item(label: str) -> QLabel:
            lbl = QLabel(label)
            lbl.setFont(lbl_font)
            lbl.setStyleSheet(f"color:{_C_BLACK}; padding-right:6px;")
            lbl.setAlignment(Qt.AlignVCenter)

            val = QLabel("--")
            val.setFont(val_font)
            val.setStyleSheet(f"color:{_C_BLACK}; padding-right:36px;")
            val.setAlignment(Qt.AlignVCenter)

            layout.addWidget(lbl)
            layout.addWidget(val)
            return val

        self._dt1_val  = add_item("ΔT1:")
        self._dt2_val  = add_item("ΔT2:")
        self._leak_val = add_item("Leak:")
        self._amb_val  = add_item("Ambient:")
        self._pres_val = add_item("Pressure:")

        layout.addStretch()

    # ------------------------------------------------------------------
    # Signal handler

    def on_sensor_updated(self, key: str, value: str) -> None:
        if key == "sensor:coolant_temp_inlet_1":
            self._inlet1 = value
            self._refresh_delta(1)
        elif key == "sensor:coolant_temp_inlet_2":
            self._inlet2 = value
            self._refresh_delta(2)
        elif key == "sensor:coolant_temp_outlet_1":
            self._outlet1 = value
            self._refresh_delta(1)
        elif key == "sensor:coolant_temp_outlet_2":
            self._outlet2 = value
            self._refresh_delta(2)
        elif key == "sensor:leak":
            if value == "NORMAL":
                self._leak_val.setText("None")
                self._leak_val.setStyleSheet(f"color:{_C_NORMAL}; padding-right:36px;")
            else:
                self._leak_val.setText("Detected")
                self._leak_val.setStyleSheet(f"color:{_C_CRITICAL}; padding-right:36px;")
        elif key == "sensor:ambient_temp":
            try:
                self._amb_temp = f"{float(value):.1f}°C"
            except ValueError:
                self._amb_temp = "--"
            self._refresh_ambient()
        elif key == "sensor:ambient_humidity":
            try:
                self._amb_hum = f"{float(value):.0f}% RH"
            except ValueError:
                self._amb_hum = "--"
            self._refresh_ambient()
        elif key == "sensor:pressure":
            try:
                self._pres_val.setText(f"{float(value):.2f} bar")
            except ValueError:
                self._pres_val.setText("--")

    # ------------------------------------------------------------------
    # Internal helpers

    def _refresh_delta(self, loop: int) -> None:
        inlet  = self._inlet1  if loop == 1 else self._inlet2
        outlet = self._outlet1 if loop == 1 else self._outlet2
        label  = self._dt1_val if loop == 1 else self._dt2_val
        try:
            delta = float(outlet) - float(inlet)
            label.setText(f"{delta:.1f}°C")
            label.setStyleSheet(f"color:{_C_BLACK}; padding-right:36px;")
        except (ValueError, TypeError):
            label.setText("--")
            label.setStyleSheet(f"color:{_C_BLACK}; padding-right:36px;")

    def _refresh_ambient(self) -> None:
        self._amb_val.setText(f"{self._amb_temp} / {self._amb_hum}")
