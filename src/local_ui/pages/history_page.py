from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHBoxLayout,
)
from PySide6.QtCore import QDateTime
from db.prometheus_client import PrometheusClient

METRICS = [
    "sensor_coolant_temp_inlet",
    "sensor_coolant_temp_outlet",
    "sensor_ambient_temp",
    "sensor_ambient_humidity",
    "sensor_pressure",
    "sensor_flow_rate",
    "sensor_water_level",
    "control_pump_duty",
    "control_fan_voltage",
    "control_cmd_pump_duty",
    "control_cmd_fan_voltage",
]

HOURS_OPTIONS = [("1h", 1), ("6h", 6), ("24h", 24), ("1 Week", 168)]


class HistoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.prometheus = PrometheusClient()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.metric_selector = QComboBox()
        self.metric_selector.addItems(METRICS)
        toolbar.addWidget(QLabel("Metric:"))
        toolbar.addWidget(self.metric_selector)

        self.hours_selector = QComboBox()
        for label, _ in HOURS_OPTIONS:
            self.hours_selector.addItem(label)
        toolbar.addWidget(QLabel("Period:"))
        toolbar.addWidget(self.hours_selector)

        btn_load = QPushButton("Query")
        btn_load.clicked.connect(self._load)
        toolbar.addWidget(btn_load)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Time", "Value"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def _load(self):
        metric = self.metric_selector.currentText()
        hours = HOURS_OPTIONS[self.hours_selector.currentIndex()][1]
        results = self.prometheus.query_range(metric, hours)

        self.table.setRowCount(0)
        if not results:
            return

        values = results[0].get("values", [])
        self.table.setRowCount(len(values))
        for row, (ts, val) in enumerate(values):
            dt = QDateTime.fromSecsSinceEpoch(int(ts)).toString("yyyy-MM-dd hh:mm:ss")
            self.table.setItem(row, 0, QTableWidgetItem(dt))
            self.table.setItem(row, 1, QTableWidgetItem(str(val)))
