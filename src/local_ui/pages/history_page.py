"""History page.

Layout:
  QHBoxLayout
  ├── Sidebar (narrow)  — Time range + Graph/Table radio + Metric checkboxes
  └── View area (main)  — Line graph (pyqtgraph) or Table (QTableWidget)

Data source: Prometheus HTTP API (/api/v1/query_range).
Step is auto-calculated to keep ~60 data points per range.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional

import requests
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QScroller
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    import pyqtgraph as pg
    _HAS_PYQTGRAPH = True
except ImportError:
    _HAS_PYQTGRAPH = False

log = logging.getLogger(__name__)

PROMETHEUS_URL = "http://localhost:9090"

# Time range options: (label, seconds)
TIME_RANGES = [
    ("5m",  5 * 60),
    ("10m", 10 * 60),
    ("30m", 30 * 60),
    ("1H",  60 * 60),
    ("6H",  6 * 60 * 60),
    ("24H", 24 * 60 * 60),
]

# Available metrics: (display name, Prometheus metric name)
METRICS = [
    ("Coolant Temp Inlet",   "coolant_temp_inlet"),
    ("Coolant Temp Outlet",  "coolant_temp_outlet"),
    ("Pressure",             "pressure"),
    ("Flow Rate",            "flow_rate"),
    ("Pump PWM Duty",        "pump_pwm_duty"),
    ("Fan PWM Duty",         "fan_pwm_duty"),
    ("Control Command",      "control_cmd"),
    ("Comm Event",           "comm_event"),
]

TARGET_POINTS = 60


class PrometheusQueryThread(QThread):
    """Runs Prometheus query in background and emits results."""

    result_ready = Signal(str, list, list)   # (metric_name, timestamps, values)
    error = Signal(str, str)                  # (metric_name, error_message)

    def __init__(self, metric: str, range_seconds: int) -> None:
        super().__init__()
        self._metric = metric
        self._range_seconds = range_seconds

    def run(self) -> None:
        end = int(time.time())
        start = end - self._range_seconds
        step = max(1, self._range_seconds // TARGET_POINTS)

        url = f"{PROMETHEUS_URL}/api/v1/query_range"
        params = {
            "query": self._metric,
            "start": start,
            "end":   end,
            "step":  step,
        }
        try:
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            results = data.get("data", {}).get("result", [])
            if not results:
                self.result_ready.emit(self._metric, [], [])
                return

            # Merge all series into one list of (ts, value) pairs
            timestamps: list[float] = []
            values: list[float] = []
            for series in results:
                for ts, val in series.get("values", []):
                    try:
                        timestamps.append(float(ts))
                        values.append(float(val))
                    except (ValueError, TypeError):
                        pass

            self.result_ready.emit(self._metric, timestamps, values)

        except Exception as e:
            self.error.emit(self._metric, str(e))


class HistoryPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._selected_metrics: set[str] = set()
        self._range_seconds = TIME_RANGES[0][1]   # default 5m
        self._show_graph = True
        self._query_threads: list[QThread] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction

    def _build_ui(self) -> None:
        self.setAutoFillBackground(True)
        self.setStyleSheet("HistoryPage { background:#ffffff; }")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ── Sidebar ────────────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setFixedWidth(320)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(4, 4, 4, 4)
        sidebar_layout.setSpacing(12)

        _ui_font = QFont()
        _ui_font.setPointSize(15)

        # Time range dropdown
        range_group = QGroupBox("Time Range")
        range_group.setFont(_ui_font)
        range_layout = QVBoxLayout(range_group)
        self._range_combo = QComboBox()
        self._range_combo.setFont(_ui_font)
        self._range_combo.setMinimumHeight(44)
        for label, _ in TIME_RANGES:
            self._range_combo.addItem(label)
        self._range_combo.currentIndexChanged.connect(self._on_range_changed)
        range_layout.addWidget(self._range_combo)
        sidebar_layout.addWidget(range_group)

        # Graph form radio
        form_group = QGroupBox("Graph Form")
        form_group.setFont(_ui_font)
        form_layout = QVBoxLayout(form_group)
        self._radio_group = QButtonGroup(self)
        self._radio_line  = QRadioButton("Line Graph")
        self._radio_table = QRadioButton("Table")
        self._radio_line.setFont(_ui_font)
        self._radio_table.setFont(_ui_font)
        self._radio_line.setChecked(True)
        self._radio_group.addButton(self._radio_line,  0)
        self._radio_group.addButton(self._radio_table, 1)
        self._radio_group.idClicked.connect(self._on_form_changed)
        form_layout.addWidget(self._radio_line)
        form_layout.addWidget(self._radio_table)
        sidebar_layout.addWidget(form_group)

        # Metric checkboxes
        metric_group = QGroupBox("Metrics")
        metric_group.setFont(_ui_font)
        metric_scroll = QScrollArea()
        metric_scroll.setWidgetResizable(True)
        metric_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        metric_scroll.setStyleSheet(
            "QScrollBar:vertical { width:20px; background:#f0f0f0; border-radius:10px; }"
            "QScrollBar::handle:vertical { background:#bdc3c7; border-radius:10px; min-height:44px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0px; }"
        )
        QScroller.grabGesture(metric_scroll.viewport(), QScroller.LeftMouseButtonGesture)
        metric_inner = QWidget()
        metric_layout = QVBoxLayout(metric_inner)
        metric_layout.setSpacing(8)
        self._checkboxes: dict[str, QCheckBox] = {}
        for display_name, metric_name in METRICS:
            cb = QCheckBox(display_name)
            cb.setFont(_ui_font)
            cb.setChecked(False)
            cb.stateChanged.connect(lambda state, m=metric_name: self._on_metric_toggled(m, state))
            self._checkboxes[metric_name] = cb
            metric_layout.addWidget(cb)
        metric_layout.addStretch()
        metric_scroll.setWidget(metric_inner)
        metric_group_layout = QVBoxLayout(metric_group)
        metric_group_layout.addWidget(metric_scroll)
        sidebar_layout.addWidget(metric_group)

        sidebar_layout.addStretch()
        layout.addWidget(sidebar)

        # ── View area ──────────────────────────────────────────────────
        self._view_container = QWidget()
        self._view_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._view_layout = QVBoxLayout(self._view_container)
        self._view_layout.setContentsMargins(0, 0, 0, 0)

        self._placeholder = QLabel("Select metrics to display")
        self._placeholder.setAlignment(Qt.AlignCenter)
        placeholder_font = QFont()
        placeholder_font.setPointSize(15)
        placeholder_font.setItalic(True)
        self._placeholder.setFont(placeholder_font)
        self._placeholder.setStyleSheet("color:#000000;")
        self._view_layout.addWidget(self._placeholder)

        layout.addWidget(self._view_container)

    # ------------------------------------------------------------------
    # Sidebar event handlers

    def _on_range_changed(self, index: int) -> None:
        self._range_seconds = TIME_RANGES[index][1]
        self._refresh()

    def _on_form_changed(self, button_id: int) -> None:
        self._show_graph = (button_id == 0)
        self._refresh()

    def _on_metric_toggled(self, metric_name: str, state: int) -> None:
        if state == Qt.Checked.value:
            self._selected_metrics.add(metric_name)
        else:
            self._selected_metrics.discard(metric_name)
        self._refresh()

    # ------------------------------------------------------------------
    # Query + render

    def _refresh(self) -> None:
        # Clear existing view
        for i in reversed(range(self._view_layout.count())):
            item = self._view_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()

        if not self._selected_metrics:
            self._placeholder = QLabel("Select metrics to display")
            self._placeholder.setAlignment(Qt.AlignCenter)
            _f = QFont()
            _f.setPointSize(15)
            _f.setItalic(True)
            self._placeholder.setFont(_f)
            self._placeholder.setStyleSheet("color:#000000;")
            self._view_layout.addWidget(self._placeholder)
            return

        # Fire a query thread per selected metric
        for metric in self._selected_metrics:
            thread = PrometheusQueryThread(metric, self._range_seconds)
            thread.result_ready.connect(self._on_result)
            thread.error.connect(self._on_query_error)
            thread.start()
            self._query_threads.append(thread)

    def _on_result(self, metric: str, timestamps: list, values: list) -> None:
        if self._show_graph:
            self._render_graph(metric, timestamps, values)
        else:
            self._render_table(metric, timestamps, values)

    def _on_query_error(self, metric: str, message: str) -> None:
        log.warning("Prometheus query error for %s: %s", metric, message)
        error_label = QLabel(f"{metric}: query failed — {message}")
        err_font = QFont()
        err_font.setPointSize(15)
        error_label.setFont(err_font)
        error_label.setStyleSheet("color:#e74c3c;")
        self._view_layout.addWidget(error_label)

    # ------------------------------------------------------------------
    # Renderers

    def _render_graph(
        self, metric: str, timestamps: list[float], values: list[float]
    ) -> None:
        if not _HAS_PYQTGRAPH:
            self._render_table(metric, timestamps, values)
            return

        plot_widget = pg.PlotWidget(title=metric)
        plot_widget.setBackground("#ffffff")
        plot_widget.showGrid(x=True, y=True, alpha=0.2)
        plot_widget.setLabel("bottom", "Time")
        plot_widget.setLabel("left", "Value")
        plot_widget.getAxis("bottom").setTextPen("#000000")
        plot_widget.getAxis("left").setTextPen("#000000")

        if timestamps and values:
            plot_widget.plot(
                timestamps, values,
                pen=pg.mkPen(color="#2980b9", width=2),
                symbol="o", symbolSize=4,
                symbolBrush="#2980b9",
            )
        else:
            plot_widget.addItem(
                pg.TextItem("No data", color="#000000", anchor=(0.5, 0.5))
            )

        self._view_layout.addWidget(plot_widget)

    def _render_table(
        self, metric: str, timestamps: list[float], values: list[float]
    ) -> None:
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)

        title = QLabel(metric)
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title.setFont(title_font)
        vbox.addWidget(title)

        table = QTableWidget(len(timestamps), 2)
        table.setHorizontalHeaderLabels(["Timestamp", "Value"])
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)

        for row, (ts, val) in enumerate(zip(timestamps, values)):
            dt_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            table.setItem(row, 0, QTableWidgetItem(dt_str))
            table.setItem(row, 1, QTableWidgetItem(f"{val:.3f}"))

        vbox.addWidget(table)
        self._view_layout.addWidget(container)
