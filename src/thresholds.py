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

# ── Delta Temperature (outlet − inlet) ────────────────────────────────────────
# docs/threshold.md § Delta Temperature
# ASHRAE TC 9.9 Liquid Cooling 권장 ΔT 10–14 °C. Warning only (critical 없음).
DELTA_TEMP_NORMAL_LO: float = 10.0
DELTA_TEMP_NORMAL_HI: float = 14.0
DELTA_TEMP_WARN_LO:   float = 10.0    # < 10 → warning (유량 과다 / 저부하)
DELTA_TEMP_WARN_HI:   float = 14.0    # > 14 → warning (유량 부족 / 과부하 / 배관 저항)


# ── Ambient (Chassis) ─────────────────────────────────────────────────────────
# docs/threshold.md § Ambient (Chassis)  — ENV-REQ-01/02
AMBIENT_TEMP_WARN_HI:  float = 40.0   # 40–45 → warning
AMBIENT_TEMP_CRIT_HI:  float = 45.0   # > 45  → critical

AMBIENT_HUM_NORMAL_LO: float = 8.0    # below → critical  (< 8 %)
AMBIENT_HUM_WARN_HI:   float = 60.0   # 60–80 → warning
AMBIENT_HUM_CRIT_HI:   float = 80.0   # > 80  → critical
AMBIENT_HUM_CRIT_LO:   float = 8.0    # < 8   → critical

# ── Chemistry (Warning only) ──────────────────────────────────────────────────
# docs/threshold.md § Chemistry  — GEN-REQ-08 / ALARM-REQ-17/18
PH_NORMAL_LO:         float = 8.0     # GEN-REQ-08 normal range lower bound
PH_NORMAL_HI:         float = 10.5    # GEN-REQ-08 normal range upper bound
PH_WARN_LO:           float = 7.8     # < 7.8 → alarm:ph_warning (ALARM-REQ-17)
CONDUCTIVITY_WARN_LO: float = 4600.0  # < 4600 µS/cm → alarm:conductivity_warning (ALARM-REQ-18)
