"""History page — Prometheus explorer style.

Layout:
  QHBoxLayout
  ├── Sidebar  — Time range + Graph form (Line/Table/Timeline) + Metric checkboxes
  └── View     — multi-series Line (pyqtgraph) or Table (QTableWidget),
                 or an "incompatible graph form" notice.

Metrics = L2A cert-sensable numeric values only (what MCG publishes to
Prometheus via src/exporter). NO water_level / leak / alarm / pH / conductivity.
All metrics are continuous-numeric → Line/Table compatible, Timeline not.

Data source: Prometheus HTTP API (/api/v1/query_range), label-aware so L1/L2/
branch series stay distinct.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

import requests
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QScrollArea,
    QScroller,
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
TARGET_POINTS = 200

# (label, seconds)
TIME_RANGES = [("15m", 900), ("30m", 1800), ("1h", 3600), ("24h", 86400)]
FORMS = ["Line", "Table", "Timeline"]

LOOP_COLOR = {"1": "#1f77b4", "2": "#9467bd"}

# Cert numeric metric registry. type 'numeric' → Line/Table ok, Timeline not.
METRICS = [
    {"id": "coolant_inlet",  "group": "Coolant Temp", "label": "Inlet",   "unit": "°C",    "query": "sensor_coolant_temp_inlet",  "dash": False},
    {"id": "coolant_outlet", "group": "Coolant Temp", "label": "Outlet",  "unit": "°C",    "query": "sensor_coolant_temp_outlet", "dash": True},
    {"id": "flow_total",     "group": "Flow",         "label": "Flow",    "unit": "L/min", "query": "sensor_flow_rate",           "dash": False},
    {"id": "flow_branch",    "group": "Flow",         "label": "Flow br", "unit": "L/min", "query": "sensor_flow_rate_branch",    "dash": True},
    {"id": "fan_rpm",        "group": "Fan",          "label": "Fan RPM", "unit": "rpm",   "query": "sensor_fan_rpm",             "dash": False},
    {"id": "pump_duty",      "group": "PWM Duty",     "label": "Pump",    "unit": "%",     "query": "sensor_pump_pwm_duty",       "dash": False},
    {"id": "fan_duty",       "group": "PWM Duty",     "label": "Fan",     "unit": "%",     "query": "sensor_fan_pwm_duty",        "dash": True},
    {"id": "ambient_temp",   "group": "Ambient",      "label": "Amb Temp", "unit": "°C",   "query": "sensor_ambient_temp",        "dash": False, "color": "#e377c2"},
    {"id": "ambient_hum",    "group": "Ambient",      "label": "Amb Hum",  "unit": "% RH", "query": "sensor_ambient_humidity",    "dash": False, "color": "#17becf"},
]
for _m in METRICS:
    _m["type"] = "numeric"
_METRIC_BY_ID = {m["id"]: m for m in METRICS}
_GROUPS = list(dict.fromkeys(m["group"] for m in METRICS))


def _form_compatible(form: str, metric: dict) -> bool:
    if form == "Table":
        return True
    if form == "Line":
        return metric["type"] != "state"
    return metric["type"] == "state"   # Timeline: state only


def _series_name(metric: dict, labels: dict) -> str:
    n = metric["label"]
    if labels.get("loop"):
        n += f" L{labels['loop']}"
    if labels.get("branch"):
        n += f"-{labels['branch']}"
    return f"{n} ({metric['unit']})"


def _series_color(metric: dict, labels: dict) -> str:
    return metric.get("color") or LOOP_COLOR.get(labels.get("loop"), "#1f77b4")


class PrometheusQueryThread(QThread):
    """Range query for one metric; emits the raw labeled result list."""

    result_ready = Signal(str, list)   # (metric_id, [ {metric:labels, values:[[t,v]]}, ... ])
    error = Signal(str, str)           # (metric_id, message)

    def __init__(self, metric_id: str, query: str, range_seconds: int) -> None:
        super().__init__()
        self._id = metric_id
        self._query = query
        self._range = range_seconds

    def run(self) -> None:
        end = int(time.time())
        start = end - self._range
        step = max(1, self._range // TARGET_POINTS)
        try:
            resp = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query_range",
                params={"query": self._query, "start": start, "end": end, "step": step},
                timeout=5,
            )
            resp.raise_for_status()
            self.result_ready.emit(self._id, resp.json().get("data", {}).get("result", []))
        except Exception as e:
            self.error.emit(self._id, str(e))


class HistoryPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._selected_ids: set[str] = {"coolant_inlet", "coolant_outlet"}
        self._range_seconds = TIME_RANGES[2][1]   # 1h
        self._form = "Line"
        self._threads: list[QThread] = []
        self._pending = 0
        self._series_buf: list[dict] = []
        self._build_ui()
        self._refresh()

    # ── UI ────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        self.setAutoFillBackground(True)
        self.setStyleSheet("HistoryPage { background:#ffffff; }")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        font = QFont(); font.setPointSize(14)

        sidebar = QWidget(); sidebar.setFixedWidth(300)
        sb = QVBoxLayout(sidebar); sb.setContentsMargins(4, 4, 4, 4); sb.setSpacing(10)

        # Time range
        rg = QGroupBox("Time Range"); rg.setFont(font)
        rl = QVBoxLayout(rg)
        self._range_combo = QComboBox(); self._range_combo.setFont(font); self._range_combo.setMinimumHeight(40)
        for label, _ in TIME_RANGES:
            self._range_combo.addItem(label)
        self._range_combo.setCurrentIndex(2)
        self._range_combo.currentIndexChanged.connect(self._on_range)
        rl.addWidget(self._range_combo)
        sb.addWidget(rg)

        # Graph form
        fg = QGroupBox("Graph Form"); fg.setFont(font)
        fl = QVBoxLayout(fg)
        self._form_group = QButtonGroup(self)
        for i, name in enumerate(FORMS):
            rb = QRadioButton(name); rb.setFont(font)
            if name == self._form:
                rb.setChecked(True)
            self._form_group.addButton(rb, i)
            fl.addWidget(rb)
        self._form_group.idClicked.connect(self._on_form)
        sb.addWidget(fg)

        # Metrics (grouped checkboxes)
        mg = QGroupBox("Metrics"); mg.setFont(font)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        QScroller.grabGesture(scroll.viewport(), QScroller.LeftMouseButtonGesture)
        inner = QWidget(); il = QVBoxLayout(inner); il.setSpacing(4)
        self._checkboxes: dict[str, QCheckBox] = {}
        for g in _GROUPS:
            gl = QLabel(g); gl.setFont(font); gl.setStyleSheet("color:#6b7280; font-weight:bold;")
            il.addWidget(gl)
            for m in (x for x in METRICS if x["group"] == g):
                cb = QCheckBox(f"  {m['label']} ({m['unit']})"); cb.setFont(font)
                cb.setChecked(m["id"] in self._selected_ids)
                cb.stateChanged.connect(lambda s, mid=m["id"]: self._on_metric(mid, s))
                self._checkboxes[m["id"]] = cb
                il.addWidget(cb)
        il.addStretch()
        scroll.setWidget(inner)
        mgl = QVBoxLayout(mg); mgl.addWidget(scroll)
        sb.addWidget(mg, stretch=1)

        layout.addWidget(sidebar)

        # View area: warning label + chart holder
        view = QWidget(); view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        vl = QVBoxLayout(view); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(6)
        self._warning = QLabel(""); self._warning.setWordWrap(True)
        self._warning.setStyleSheet("color:#b45309; background:#fffbeb; border:1px solid #fde68a; border-radius:8px; padding:8px;")
        self._warning.setFont(font); self._warning.hide()
        vl.addWidget(self._warning)
        self._chart_holder = QWidget()
        self._chart_layout = QVBoxLayout(self._chart_holder)
        self._chart_layout.setContentsMargins(0, 0, 0, 0)
        vl.addWidget(self._chart_holder, stretch=1)
        layout.addWidget(view, stretch=1)

    # ── events ────────────────────────────────────────────────────────
    def _on_range(self, idx: int) -> None:
        self._range_seconds = TIME_RANGES[idx][1]
        self._refresh()

    def _on_form(self, fid: int) -> None:
        self._form = FORMS[fid]
        self._refresh()

    def _on_metric(self, mid: str, state: int) -> None:
        if state == Qt.Checked.value:
            self._selected_ids.add(mid)
        else:
            self._selected_ids.discard(mid)
        self._refresh()

    # ── query + render ────────────────────────────────────────────────
    def _clear_chart(self) -> None:
        for i in reversed(range(self._chart_layout.count())):
            w = self._chart_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

    def _show_message(self, text: str, color: str = "#6b7280") -> None:
        self._clear_chart()
        lbl = QLabel(text); lbl.setAlignment(Qt.AlignCenter)
        f = QFont(); f.setPointSize(15); lbl.setFont(f)
        lbl.setStyleSheet(f"color:{color};")
        self._chart_layout.addWidget(lbl)

    def _refresh(self) -> None:
        selected = [_METRIC_BY_ID[i] for i in self._selected_ids]
        incompatible = [m for m in selected if not _form_compatible(self._form, m)]
        renderable = [m for m in selected if _form_compatible(self._form, m)]

        if incompatible:
            names = ", ".join(m["label"] for m in incompatible)
            self._warning.setText(
                f"Incompatible graph form: {names} cannot be shown as {self._form}. (use Line/Table)")
            self._warning.show()
        else:
            self._warning.hide()

        if not selected:
            self._warning.hide()
            self._show_message("Select a metric on the left.")
            return
        if not renderable:
            self._show_message(f"The selected metrics are not compatible with the {self._form} form.")
            return

        self._show_message("loading…")
        self._series_buf = []
        self._pending = len(renderable)
        self._threads = []
        for m in renderable:
            t = PrometheusQueryThread(m["id"], m["query"], self._range_seconds)
            t.result_ready.connect(self._on_result)
            t.error.connect(self._on_error)
            t.start()
            self._threads.append(t)

    def _on_result(self, metric_id: str, result: list) -> None:
        m = _METRIC_BY_ID.get(metric_id)
        if m:
            for s in result:
                labels = s.get("metric", {})
                data = []
                for ts, val in s.get("values", []):
                    try:
                        data.append((float(ts), float(val)))
                    except (ValueError, TypeError):
                        pass
                self._series_buf.append({
                    "name": _series_name(m, labels),
                    "color": _series_color(m, labels),
                    "dash": m["dash"],
                    "data": data,
                })
        self._pending -= 1
        if self._pending <= 0:
            self._render()

    def _on_error(self, metric_id: str, message: str) -> None:
        log.warning("Prometheus query error %s: %s", metric_id, message)
        self._pending -= 1
        if self._pending <= 0:
            self._render()

    def _render(self) -> None:
        series = [s for s in self._series_buf if s["data"]]
        if not series:
            self._show_message("No data in range.")
            return
        if self._form == "Table":
            self._render_table(series)
        else:
            self._render_line(series)

    def _render_line(self, series: list[dict]) -> None:
        self._clear_chart()
        if not _HAS_PYQTGRAPH:
            self._render_table(series)
            return
        axis = pg.DateAxisItem(orientation="bottom")
        plot = pg.PlotWidget(axisItems={"bottom": axis})
        plot.setBackground("#ffffff")
        plot.showGrid(x=True, y=True, alpha=0.2)
        plot.getAxis("bottom").setTextPen("#000000")
        plot.getAxis("left").setTextPen("#000000")
        plot.addLegend(offset=(10, 10))
        for s in series:
            xs = [p[0] for p in s["data"]]
            ys = [p[1] for p in s["data"]]
            style = Qt.DashLine if s["dash"] else Qt.SolidLine
            plot.plot(xs, ys, pen=pg.mkPen(color=s["color"], width=2, style=style), name=s["name"])
        self._chart_layout.addWidget(plot)

    def _render_table(self, series: list[dict]) -> None:
        self._clear_chart()
        # union of timestamps, descending (newest first)
        ts_set = sorted({p[0] for s in series for p in s["data"]}, reverse=True)
        maps = [dict(s["data"]) for s in series]
        table = QTableWidget(len(ts_set), 1 + len(series))
        table.setHorizontalHeaderLabels(["Timestamp"] + [s["name"] for s in series])
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        for row, ts in enumerate(ts_set):
            table.setItem(row, 0, QTableWidgetItem(
                datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")))
            for col, m in enumerate(maps, start=1):
                v = m.get(ts)
                table.setItem(row, col, QTableWidgetItem("" if v is None else f"{v:.2f}"))
        self._chart_layout.addWidget(table)
