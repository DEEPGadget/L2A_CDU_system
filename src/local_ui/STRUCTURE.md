# local_ui — Module Structure

PySide6-based kiosk UI for the L2A CDU system.
Runs on Raspberry Pi Touch Display 2 (1280×720, touch).

---

## Directory Layout

```
src/local_ui/
├── STRUCTURE.md              # This file
├── main.py                   # Entry point
├── redis_subscriber.py       # Redis Pub/Sub listener thread
│
├── pages/                    # Full-screen page widgets (QStackedWidget slots)
│   ├── monitoring_page.py    # Monitoring & Control page
│   └── history_page.py       # History (graph / table) page
│
├── widgets/                  # Reusable UI components
│   ├── top_bar.py            # Top navigation bar (tabs, alarm badge, status, clock)
│   ├── cooling_health.py     # Cooling circuit SVG diagram + pump/fan overlay controls
│   ├── status_strip.py       # Bottom status bar (ΔT1, ΔT2, Total Flow, Ambient, (Leak placeholder))
│   ├── alarm_overlay.py      # Floating alarm list panel
│   └── control_panel.py      # NumpadDialog — PWM duty input popup (0–100)
│
└── assets/
    └── cooling_health.svg    # SVG template for the cooling circuit diagram
```

---

## File Descriptions

### Entry Point

| File | Description |
|---|---|
| `main.py` | Initialises Redis, starts `RedisSubscriber` thread, builds `MainWindow` (TopBar + QStackedWidget), wires signals, shows fullscreen window. Startup sequence documented in file docstring. |

---

### Data Layer

| File | Description |
|---|---|
| `redis_subscriber.py` | Background `QThread`. Subscribes to Redis Pub/Sub (`sensor:*`, `comm:*`) and keyspace events (`alarm:*`). Emits Qt signals: `sensor_updated`, `comm_updated`, `alarm_set`, `alarm_deleted`. All UI updates are driven by these signals. |

---

### Pages

| File | Description |
|---|---|
| `pages/monitoring_page.py` | Main operational view. Stacks `CoolingHealthWidget` (stretch) above `StatusStripWidget` (fixed 60px). Hosts `AlarmOverlayWidget` as a floating child (not in layout). Handles tap-outside dismissal of the overlay via `eventFilter`. |
| `pages/history_page.py` | Historical data view. Sidebar (time range, graph/table toggle, metric checkboxes) + main view area (pyqtgraph line chart or `QTableWidget`). Queries Prometheus `/api/v1/query_range`; step auto-calculated to keep ~60 data points per range. |

---

### Widgets

| File | Description |
|---|---|
| `widgets/top_bar.py` | Fixed 52px bar across the top. Left: `Monitoring` / `History` / `Settings` tab buttons. Centre: alarm badge (`🔔 N`, hidden when no alarms), IP address, `System:` status (bold, colour-coded), `Link:` status (bold, colour-coded), `Manual/Auto` mode toggle. Right: `HH:MM:SS` clock (1 s tick). |
| `widgets/cooling_health.py` | Loads `cooling_health.svg` as a string template, substitutes `{PLACEHOLDER}` values and `{PLACEHOLDER_C}` colour tokens on every sensor update, then reloads into `QSvgWidget`. Transparent `QPushButton` overlays sit on top of the Pump and Fan+Radiator boxes; tapping opens `NumpadDialog`. On startup, reads current Redis values directly (GET) to avoid missing the initial Pub/Sub publish. Threshold colours sourced from `src/thresholds.py`. |
| `widgets/status_strip.py` | Fixed 76px bottom bar. Displays ΔT1, ΔT2 (computed outlet − inlet), Total Flow, Ambient Temp/Humidity, and a 5th placeholder slot reserved for Leak (D1). Updated via `on_sensor_updated()`. |
| `widgets/alarm_overlay.py` | Floating panel, child of `MonitoringPage` but outside the layout. Shows active alarm list. Appears when alarm badge is tapped; auto-closes when all alarms clear. |
| `widgets/control_panel.py` | `NumpadDialog` — modal `QDialog` with a 3×4 numpad grid (0–9, ⌫, C), value display, and Apply / Cancel buttons. Validates 0–100 range on Apply. Used by `CoolingHealthWidget` overlay taps. |

---

### Assets

| File | Description |
|---|---|
| `assets/cooling_health.svg` | SVG template for the cooling circuit diagram (canvas 1280×608). Contains `{PLACEHOLDER}` tokens for sensor values and `{PLACEHOLDER_C}` tokens for colour substitution. Not rendered directly — loaded as a string by `CoolingHealthWidget`. |

---

## Signal Flow

```
Redis Pub/Sub
    │
    ▼
RedisSubscriber (QThread)
    ├── sensor_updated  →  MonitoringPage → CoolingHealthWidget, StatusStripWidget
    ├── comm_updated    →  TopBarWidget
    ├── alarm_set       →  TopBarWidget, MonitoringPage → AlarmOverlayWidget
    └── alarm_deleted   →  TopBarWidget, MonitoringPage → AlarmOverlayWidget
```

## Related Files (outside local_ui)

| File | Role |
|---|---|
| `src/thresholds.py` | Sensor threshold constants (single source of truth for alarm boundaries) |
| `src/config.py` | App mode loader (`fake` / `real`) from `config/config.yaml` |
| `docs/UI_Design.md` | UI layout spec, design principles, component data mapping |
| `docs/threshold.md` | Human-readable threshold reference and code update pipeline |
