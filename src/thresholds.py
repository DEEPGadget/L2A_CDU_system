"""Sensor threshold constants.

Single source of truth for all alarm boundary values on the code side.
Keep in sync with docs/threshold.md whenever values change.

Referenced by:
  - src/local_ui/widgets/cooling_health.py  (UI color logic)
  - src/fake_data/scenarios.py              (simulator drift ranges)
"""

# ── Coolant Temperature — Inlet ───────────────────────────────────────────────
# docs/threshold.md § Coolant Temperature
INLET_TEMP_NORMAL_LO: float = 22.0
INLET_TEMP_NORMAL_HI: float = 40.0
INLET_TEMP_WARN_LO:   float = 18.0   # below → warning
INLET_TEMP_WARN_HI:   float = 45.0   # above → warning (>40 warning, >45 critical)
INLET_TEMP_CRIT_LO:   float = 18.0   # below → critical
INLET_TEMP_CRIT_HI:   float = 45.0   # above → critical

# ── Coolant Temperature — Outlet ──────────────────────────────────────────────
# docs/threshold.md § Coolant Temperature
OUTLET_TEMP_NORMAL_HI: float = 60.0
OUTLET_TEMP_WARN_HI:   float = 65.0   # 60–65 → warning
OUTLET_TEMP_CRIT_HI:   float = 65.0   # > 65  → critical  (ALARM-REQ-04)
OUTLET_TEMP_CRIT_LO:   float = 18.0   # < 18  → critical  (condensation risk below dew point)
OUTLET_TEMP_WARN_LO:   float = 22.0   # < 22  → warning

# ── Delta Temperature (computed: outlet − inlet) ──────────────────────────────
# docs/threshold.md § Delta Temperature
DELTA_TEMP_WARN_HI:  float = 15.0   # 15–20 → warning
DELTA_TEMP_CRIT_HI:  float = 20.0   # > 20  → critical

# ── Ambient (Chassis) ─────────────────────────────────────────────────────────
# docs/threshold.md § Ambient (Chassis)  — ENV-REQ-01/02
AMBIENT_TEMP_WARN_HI:  float = 40.0   # 40–45 → warning
AMBIENT_TEMP_CRIT_HI:  float = 45.0   # > 45  → critical

AMBIENT_HUM_NORMAL_LO: float = 8.0    # below → critical  (< 8 %)
AMBIENT_HUM_WARN_HI:   float = 60.0   # 60–80 → warning
AMBIENT_HUM_CRIT_HI:   float = 80.0   # > 80  → critical
AMBIENT_HUM_CRIT_LO:   float = 8.0    # < 8   → critical

# ── Chemistry (Warning only) ──────────────────────────────────────────────────
# docs/threshold.md § Chemistry  — ALARM-REQ-17/18
PH_WARN_LO:           float = 7.8     # < 7.8 → warning
CONDUCTIVITY_WARN_LO: float = 4600.0  # < 4600 µs → warning
