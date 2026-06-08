"""History page — Prometheus explorer style (mirrors the Web History page).

Layout:
  QHBoxLayout
  ├── Sidebar  — Time range (default 30m) + Graph form (Line/Table/Timeline)
  │             + grouped metric checkboxes (default: Coolant Temp).
  └── View     — warning banner + scrollable stack of per-(group, unit) charts
                 (pyqtgraph), or a single Table, or an incompatible-form notice.

Each Line chart:
  * one panel per (group, unit) — a group splits further when it mixes units
    (e.g. Ambient = °C + % RH), so the Y axis is never distorted;
  * x-axis spans the whole selected window (lines drawn only where data exists);
  * thin lines, a distinct colour per series, no dots;
  * a Name / Min / Max / Mean legend;
  * a drag crosshair that shows each series' value at the touched time.

Metrics = L2A cert-sensable numeric values only (what MCG publishes to
Prometheus via src/exporter). NO water_level / leak / alarm / pH / conductivity.
All metrics are continuous-numeric → Line/Table compatible, Timeline not.
Data: Prometheus /api/v1/query_range at 1-minute resolution, label-aware.
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
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
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

    class _TimeAxis(pg.DateAxisItem):
        """Bottom time axis showing HH:MM only (no weekday/date — the range
        label above the charts carries the date)."""

        def tickStrings(self, values, scale, spacing):
            out = []
            for v in values:
                try:
                    out.append(datetime.fromtimestamp(v).strftime("%H:%M"))
                except (ValueError, OSError, OverflowError):
                    out.append("")
            return out
except ImportError:
    _HAS_PYQTGRAPH = False

log = logging.getLogger(__name__)

PROMETHEUS_URL = "http://localhost:9090"
STEP_SECONDS = 60  # 1-minute resolution (matches the Web History page)

# (label, seconds)
TIME_RANGES = [("15m", 900), ("30m", 1800), ("1h", 3600), ("24h", 86400)]
FORMS = ["Line", "Table", "Timeline"]

# Distinct colour per selected series (no dashes) — mirrors the Web palette.
PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b",
           "#e377c2", "#17becf", "#bcbd22", "#393b79", "#637939", "#8c6d31"]

# Cert numeric metric registry. type 'numeric' → Line/Table ok, Timeline not.
METRICS = [
    {"id": "coolant_inlet",  "group": "Coolant Temp", "label": "Inlet",   "unit": "°C",    "query": "sensor_coolant_temp_inlet"},
    {"id": "coolant_outlet", "group": "Coolant Temp", "label": "Outlet",  "unit": "°C",    "query": "sensor_coolant_temp_outlet"},
    {"id": "delta_t",        "group": "Coolant Temp", "label": "ΔT",      "unit": "°C",    "query": "sensor_coolant_temp_delta"},
    {"id": "flow_1",         "group": "Flow",         "label": "Flow L1", "unit": "L/min", "query": 'sensor_flow_rate{loop="1"}', "no_auto_loop": True},
    {"id": "flow_2",         "group": "Flow",         "label": "Flow L2", "unit": "L/min", "query": 'sensor_flow_rate{loop="2"}', "no_auto_loop": True},
    {"id": "flow_branch",    "group": "Flow",         "label": "Flow branch", "unit": "L/min", "query": "sensor_flow_rate_branch"},
    {"id": "fan_rpm",        "group": "Fan",          "label": "Fan RPM", "unit": "RPM",   "query": "sensor_fan_rpm"},
    {"id": "pump_duty",      "group": "PWM Duty",     "label": "Pump",    "unit": "%",     "query": "sensor_pump_pwm_duty"},
    {"id": "fan_duty",       "group": "PWM Duty",     "label": "Fan",     "unit": "%",     "query": "sensor_fan_pwm_duty"},
    {"id": "ambient_temp",   "group": "Ambient",      "label": "Amb Temp", "unit": "°C",   "query": "sensor_ambient_temp"},
    {"id": "ambient_hum",    "group": "Ambient",      "label": "Amb Hum",  "unit": "% RH", "query": "sensor_ambient_humidity"},
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
    if metric.get("no_auto_loop"):   # label already encodes the loop (e.g. "Flow L1")
        return f"{metric['label']} ({metric['unit']})"
    n = metric["label"]
    if labels.get("loop"):
        n += f" L{labels['loop']}"
    if labels.get("branch"):
        n += f"-{labels['branch']}"
    return f"{n} ({metric['unit']})"


class PrometheusQueryThread(QThread):
    """Range query for one metric over a shared [start, end] grid."""

    result_ready = Signal(str, list)   # (metric_id, [ {metric:labels, values:[[t,v]]}, ... ])
    error = Signal(str, str)           # (metric_id, message)

    def __init__(self, metric_id: str, query: str, start: int, end: int, step: int) -> None:
        super().__init__()
        self._id = metric_id
        self._query = query
        self._start = start
        self._end = end
        self._step = step

    def run(self) -> None:
        try:
            resp = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query_range",
                params={"query": self._query, "start": self._start, "end": self._end, "step": self._step},
                timeout=5,
            )
            resp.raise_for_status()
            self.result_ready.emit(self._id, resp.json().get("data", {}).get("result", []))
        except Exception as e:
            self.error.emit(self._id, str(e))


class ChartPanel(QWidget):
    """One titled plot for a single (group, unit): thin lines, full-range x,
    Min/Max/Mean legend, and a drag crosshair tooltip."""

    def __init__(self, title: str, series: list[dict], t_start: int, t_end: int, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("ChartPanel")
        self.setStyleSheet("#ChartPanel { background:#ffffff; border:1px solid #e5e7eb; border-radius:6px; }")
        self._series = series
        self._t_start = t_start
        self._t_end = t_end
        self._maps = [dict(s["data"]) for s in series]
        self._all_ts = sorted({p[0] for s in series for p in s["data"]})
        allv = [p[1] for s in series for p in s["data"]]
        self._dec = 1 if (allv and (max(allv) - min(allv)) < 5) else 0

        v = QVBoxLayout(self)
        v.setContentsMargins(8, 6, 8, 6)
        v.setSpacing(3)

        tf = QFont(); tf.setPointSize(14); tf.setBold(True)
        tl = QLabel(title); tl.setFont(tf); tl.setStyleSheet("color:#000000; border:none;")
        v.addWidget(tl)

        if _HAS_PYQTGRAPH:
            self._build_plot(v)
        if not self._all_ts:
            empty = QLabel("No data in range"); empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color:#9ca3af; border:none; padding:24px;")
            v.addWidget(empty)
        else:
            v.addWidget(self._build_legend())

    def _build_plot(self, v: QVBoxLayout) -> None:
        axis = _TimeAxis(orientation="bottom")
        self._plot = pg.PlotWidget(axisItems={"bottom": axis})
        self._plot.setBackground("#ffffff")
        self._plot.setMinimumHeight(190)
        self._plot.showGrid(x=True, y=True, alpha=0.12)
        tickfont = QFont(); tickfont.setPointSize(12)
        for ax in ("bottom", "left"):
            self._plot.getAxis(ax).setTextPen("#000000")
            self._plot.getAxis(ax).setStyle(tickFont=tickfont)
        self._plot.setMouseEnabled(x=False, y=False)
        self._plot.hideButtons()
        vb = self._plot.getPlotItem().getViewBox()
        vb.setMenuEnabled(False)
        self._plot.setXRange(self._t_start, self._t_end, padding=0.0)

        for s in self._series:
            if s["data"]:
                xs = [p[0] for p in s["data"]]
                ys = [p[1] for p in s["data"]]
                self._plot.plot(xs, ys, pen=pg.mkPen(color=s["color"], width=2.5))

        # crosshair (driven by drag/move on the touch panel)
        self._vline = pg.InfiniteLine(angle=90, movable=False,
                                      pen=pg.mkPen("#bbbbbb", style=Qt.DashLine))
        self._vline.hide()
        self._plot.addItem(self._vline, ignoreBounds=True)
        self._text = pg.TextItem(anchor=(0, 1))
        self._text.hide()
        self._plot.addItem(self._text, ignoreBounds=True)
        if self._all_ts:
            self._plot.scene().sigMouseMoved.connect(self._on_mouse)
        v.addWidget(self._plot)

    def _build_legend(self) -> QWidget:
        w = QWidget(); w.setStyleSheet("border:none;")
        g = QGridLayout(w)
        g.setContentsMargins(2, 0, 2, 0)
        g.setHorizontalSpacing(12); g.setVerticalSpacing(1)
        hf = QFont(); hf.setPointSize(13)
        for c, h in enumerate(["Name", "Min", "Max", "Mean"]):
            lab = QLabel(h); lab.setFont(hf); lab.setStyleSheet("color:#000000; border:none;")
            if c > 0:
                lab.setAlignment(Qt.AlignRight)
            g.addWidget(lab, 0, c)
        g.setColumnStretch(0, 1)
        for r, s in enumerate(self._series, start=1):
            vs = [p[1] for p in s["data"]]
            name = QLabel(f"<span style='color:{s['color']}'>■</span> {s['name']}")
            name.setFont(hf); name.setStyleSheet("color:#000000; border:none;")
            g.addWidget(name, r, 0)
            if vs:
                stats = [f"{min(vs):.{self._dec}f}", f"{max(vs):.{self._dec}f}",
                         f"{sum(vs) / len(vs):.{self._dec}f}"]
            else:
                stats = ["–", "–", "–"]
            for c, val in enumerate(stats, start=1):
                lab = QLabel(val); lab.setFont(hf); lab.setAlignment(Qt.AlignRight)
                lab.setStyleSheet("color:#000000; border:none;")
                g.addWidget(lab, r, c)
        return w

    def _on_mouse(self, pos) -> None:
        vb = self._plot.getPlotItem().getViewBox()
        if not self._plot.sceneBoundingRect().contains(pos):
            self._vline.hide(); self._text.hide(); return
        x = vb.mapSceneToView(pos).x()
        nearest = min(self._all_ts, key=lambda t: abs(t - x))
        self._vline.setPos(nearest); self._vline.show()
        ts_label = datetime.fromtimestamp(nearest).strftime("%m-%d %H:%M")
        html = [f"<div style='font-size:12pt; background:#ffffffee;'>"
                f"<b style='color:#000000'>{ts_label}</b>"]
        for s, m in zip(self._series, self._maps):
            val = m.get(nearest)
            if val is None:
                continue
            html.append(f"<br><span style='color:{s['color']}'>■</span> "
                        f"<span style='color:#000000'>{s['name']}: {val:.{self._dec}f}</span>")
        html.append("</div>")
        self._text.setHtml("".join(html))
        mid = (self._t_start + self._t_end) / 2
        self._text.setAnchor((0, 1) if nearest < mid else (1, 1))
        ytop = vb.viewRange()[1][1]
        self._text.setPos(nearest, ytop)
        self._text.show()


class HistoryPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._selected_ids: set[str] = {"coolant_inlet", "coolant_outlet", "flow_1", "flow_2"}
        self._range_seconds = TIME_RANGES[1][1]   # 30m default
        self._form = "Line"
        self._threads: list[QThread] = []
        self._pending = 0
        self._series_buf: list[dict] = []
        self._win_start = 0
        self._win_end = 0
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
        # Explicit colours so the popup items aren't white-on-white on the kiosk.
        self._range_combo.setStyleSheet(
            "QComboBox { color:#111827; background:#ffffff; padding:4px 8px; }"
            "QComboBox QAbstractItemView { color:#111827; background:#ffffff;"
            " selection-background-color:#1f77b4; selection-color:#ffffff; outline:0; }"
            "QComboBox QAbstractItemView::item { min-height:44px; padding:4px 8px; }"
        )
        for label, _ in TIME_RANGES:
            self._range_combo.addItem(label)
        self._range_combo.setCurrentIndex(1)   # 30m
        self._range_combo.currentIndexChanged.connect(self._on_range)
        rl.addWidget(self._range_combo)
        sb.addWidget(rg)

        # Graph form (touch-friendly: roomy rows + larger indicators)
        fg = QGroupBox("Graph Form"); fg.setFont(font)
        fl = QVBoxLayout(fg); fl.setSpacing(10)
        self._form_group = QButtonGroup(self)
        for i, name in enumerate(FORMS):
            rb = QRadioButton(name); rb.setFont(font)
            rb.setMinimumHeight(46)
            rb.setStyleSheet("QRadioButton::indicator { width:26px; height:26px; }")
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
        inner = QWidget(); il = QVBoxLayout(inner); il.setSpacing(8)
        self._checkboxes: dict[str, QCheckBox] = {}
        for g in _GROUPS:
            gl = QLabel(g); gl.setFont(font); gl.setStyleSheet("color:#6b7280; font-weight:bold;")
            il.addWidget(gl)
            for m in (x for x in METRICS if x["group"] == g):
                cb = QCheckBox(f"  {m['label']} ({m['unit']})"); cb.setFont(font)
                cb.setMinimumHeight(40)
                cb.setStyleSheet("QCheckBox::indicator { width:26px; height:26px; }")
                cb.setChecked(m["id"] in self._selected_ids)
                cb.stateChanged.connect(lambda s, mid=m["id"]: self._on_metric(mid, s))
                self._checkboxes[m["id"]] = cb
                il.addWidget(cb)
        il.addStretch()
        scroll.setWidget(inner)
        mgl = QVBoxLayout(mg); mgl.addWidget(scroll)
        sb.addWidget(mg, stretch=1)

        layout.addWidget(sidebar)

        # View area: warning banner + selected-window label + scrollable charts
        view = QWidget(); view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        vl = QVBoxLayout(view); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(6)

        self._range_label = QLabel("")
        rf = QFont(); rf.setPointSize(11); self._range_label.setFont(rf)
        self._range_label.setStyleSheet("color:#6b7280;")
        vl.addWidget(self._range_label)

        self._warning = QLabel(""); self._warning.setWordWrap(True)
        self._warning.setStyleSheet("color:#b45309; background:#fffbeb; border:1px solid #fde68a; border-radius:8px; padding:8px;")
        self._warning.setFont(font); self._warning.hide()
        vl.addWidget(self._warning)

        self._chart_scroll = QScrollArea(); self._chart_scroll.setWidgetResizable(True)
        self._chart_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._chart_scroll.setStyleSheet("QScrollArea { border:none; }")
        QScroller.grabGesture(self._chart_scroll.viewport(), QScroller.LeftMouseButtonGesture)
        holder = QWidget()
        self._chart_layout = QVBoxLayout(holder)
        self._chart_layout.setContentsMargins(0, 0, 0, 0)
        self._chart_layout.setSpacing(8)
        self._chart_scroll.setWidget(holder)
        vl.addWidget(self._chart_scroll, stretch=1)
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
        while self._chart_layout.count():
            item = self._chart_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _show_message(self, text: str, color: str = "#9ca3af") -> None:
        self._clear_chart()
        lbl = QLabel(text); lbl.setAlignment(Qt.AlignCenter)
        f = QFont(); f.setPointSize(15); lbl.setFont(f)
        lbl.setStyleSheet(f"color:{color};")
        self._chart_layout.addWidget(lbl)
        self._chart_layout.addStretch()

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
            self._range_label.setText("")
            self._show_message("Select a metric on the left.")
            return
        if not renderable:
            self._range_label.setText("")
            self._show_message(f"The selected metrics are not compatible with the {self._form} form.")
            return

        # One absolute [start, end] grid for every metric query (so timestamps
        # line up across series — minute-aligned).
        end = int(time.time())
        end -= end % STEP_SECONDS
        start = end - self._range_seconds
        self._win_start, self._win_end = start, end
        self._range_label.setText(
            f"{datetime.fromtimestamp(start):%Y-%m-%d %H:%M} ~ "
            f"{datetime.fromtimestamp(end):%Y-%m-%d %H:%M}")

        self._show_message("loading…")
        self._series_buf = []
        self._pending = len(renderable)
        self._threads = []
        for m in renderable:
            t = PrometheusQueryThread(m["id"], m["query"], start, end, STEP_SECONDS)
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
                    "group": m["group"],
                    "unit": m["unit"],
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
        # Distinct colour per series (sorted by name → stable palette mapping).
        series_all = sorted(self._series_buf, key=lambda s: s["name"])
        for i, s in enumerate(series_all):
            s["color"] = PALETTE[i % len(PALETTE)]

        if self._form == "Table":
            data_series = [s for s in series_all if s["data"]]
            if not data_series:
                self._show_message("No data in range.")
                return
            self._render_table(data_series)
            return

        # Line: one panel per (group, unit) among the selected renderable metrics.
        self._clear_chart()
        renderable = [_METRIC_BY_ID[i] for i in self._selected_ids
                      if _form_compatible(self._form, _METRIC_BY_ID[i])]
        panels: list[tuple[str, list[dict]]] = []
        for g in _GROUPS:
            units: list[str] = []
            for m in renderable:
                if m["group"] == g and m["unit"] not in units:
                    units.append(m["unit"])
            for u in units:
                sers = [s for s in series_all if s["group"] == g and s["unit"] == u]
                panels.append((f"{g} ({u})", sers))

        if not panels:
            self._show_message("No data in range.")
            return
        for title, sers in panels:
            self._chart_layout.addWidget(ChartPanel(title, sers, self._win_start, self._win_end))
        self._chart_layout.addStretch()

    def _render_table(self, series: list[dict]) -> None:
        self._clear_chart()
        ts_set = sorted({p[0] for s in series for p in s["data"]}, reverse=True)
        maps = [dict(s["data"]) for s in series]
        table = QTableWidget(len(ts_set), 1 + len(series))
        table.setHorizontalHeaderLabels(["Time"] + [s["name"] for s in series])
        tf = QFont(); tf.setPointSize(13)
        table.setFont(tf)
        table.horizontalHeader().setFont(tf)
        table.verticalHeader().setDefaultSectionSize(38)
        # Size each column to its content/header so titles are never truncated.
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        QScroller.grabGesture(table.viewport(), QScroller.LeftMouseButtonGesture)
        for row, ts in enumerate(ts_set):
            table.setItem(row, 0, QTableWidgetItem(
                datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")))
            for col, m in enumerate(maps, start=1):
                v = m.get(ts)
                table.setItem(row, col, QTableWidgetItem("" if v is None else f"{v:.2f}"))
        self._chart_layout.addWidget(table)
