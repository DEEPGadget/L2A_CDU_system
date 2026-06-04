"""Redis key constants used by MCG.

Single source of truth. UI and tests also import from here (eventually) to
avoid string typos. See docs/MCG.md "Redis Key" section for the full table.

Persistence (RDB + AOF) is enabled on the Redis instance, so `control:*` and
`sensor:*_duty_*` are restored after a restart. Other `sensor:*` keys are
re-published by MCG on every poll cycle.
"""

from __future__ import annotations

# ── Sensor (PCB input registers + derived) ────────────────────────────────────
SENSOR_COOLANT_TEMP_INLET_1  = "sensor:coolant_temp_inlet_1"
SENSOR_COOLANT_TEMP_INLET_2  = "sensor:coolant_temp_inlet_2"
SENSOR_COOLANT_TEMP_OUTLET_1 = "sensor:coolant_temp_outlet_1"
SENSOR_COOLANT_TEMP_OUTLET_2 = "sensor:coolant_temp_outlet_2"

SENSOR_FAN_RPM_1 = "sensor:fan_rpm_1"
SENSOR_FAN_RPM_2 = "sensor:fan_rpm_2"

# Flow — 4 branch sensors (2 per loop, VVX15 on AIN1~4=IR 32~35), summed to
# per-loop totals. Both the totals and the 4 branch values are published.
# See polling._read_flow_lpm(). Loop1 = branch 1_1 + 1_2, Loop2 = 2_1 + 2_2.
SENSOR_FLOW_RATE_1 = "sensor:flow_rate_1"      # loop 1 total
SENSOR_FLOW_RATE_2 = "sensor:flow_rate_2"      # loop 2 total
SENSOR_FLOW_RATE_1_1 = "sensor:flow_rate_1_1"  # loop 1 branch 1 (AIN1)
SENSOR_FLOW_RATE_1_2 = "sensor:flow_rate_1_2"  # loop 1 branch 2 (AIN2)
SENSOR_FLOW_RATE_2_1 = "sensor:flow_rate_2_1"  # loop 2 branch 1 (AIN3)
SENSOR_FLOW_RATE_2_2 = "sensor:flow_rate_2_2"  # loop 2 branch 2 (AIN4)
# (total_key, (branch1_key, branch2_key)) per loop — iteration helper
FLOW_LOOPS = (
    (SENSOR_FLOW_RATE_1, (SENSOR_FLOW_RATE_1_1, SENSOR_FLOW_RATE_1_2)),
    (SENSOR_FLOW_RATE_2, (SENSOR_FLOW_RATE_2_1, SENSOR_FLOW_RATE_2_2)),
)

SENSOR_WATER_LEVEL = "sensor:water_level"
SENSOR_LEAK        = "sensor:leak"

SENSOR_AMBIENT_TEMP     = "sensor:ambient_temp"
SENSOR_AMBIENT_HUMIDITY = "sensor:ambient_humidity"

# ── Duty (UI <-> MCG) ─────────────────────────────────────────────────────────
SENSOR_PUMP_PWM_DUTY_1 = "sensor:pump_pwm_duty_1"
SENSOR_PUMP_PWM_DUTY_2 = "sensor:pump_pwm_duty_2"
SENSOR_FAN_PWM_DUTY_1  = "sensor:fan_pwm_duty_1"
SENSOR_FAN_PWM_DUTY_2  = "sensor:fan_pwm_duty_2"

# Iteration helpers
PUMP_DUTY_KEYS = (SENSOR_PUMP_PWM_DUTY_1, SENSOR_PUMP_PWM_DUTY_2)
FAN_DUTY_KEYS  = (SENSOR_FAN_PWM_DUTY_1,  SENSOR_FAN_PWM_DUTY_2)

# ── Communication state ───────────────────────────────────────────────────────
COMM_STATUS               = "comm:status"               # ok / timeout / disconnected
COMM_CONSECUTIVE_FAILURES = "comm:consecutive_failures"
COMM_LAST_ERROR           = "comm:last_error"

# ── Control (mode + auto params) — persistent ─────────────────────────────────
CONTROL_MODE       = "control:mode"               # string: manual / auto / emergency
CONTROL_FAN_CURVE  = "control:fan_curve"          # hash: min_temp/max_temp/min_duty/max_duty
CONTROL_PUMP_DUTY  = "control:pump_duty"          # string: 0~1000 (x10 integer)

# ── Pub/Sub channels (control updates) ────────────────────────────────────────
CH_CONTROL_MODE              = "control:mode"
CH_CONTROL_FAN_CURVE_UPDATE  = "control:fan_curve:update"
CH_CONTROL_PUMP_DUTY_UPDATE  = "control:pump_duty:update"

CONTROL_CHANNELS = (
    CH_CONTROL_MODE,
    CH_CONTROL_FAN_CURVE_UPDATE,
    CH_CONTROL_PUMP_DUTY_UPDATE,
)
