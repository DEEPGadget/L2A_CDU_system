# Sensor Thresholds

Alarm boundary values referenced by Redis key names.
Used as the source of truth for `src/fake_data/scenarios.py` and alarm manager logic.

## Coolant Temperature

| Redis Key | Normal | Warning | Critical |
|---|---|---|---|
| `sensor:coolant_temp_inlet_1` | 22–40 °C | 18–21 °C or 41–45 °C | < 18 °C or > 45 °C |
| `sensor:coolant_temp_inlet_2` | 22–40 °C | 18–21 °C or 41–45 °C | < 18 °C or > 45 °C |
| `sensor:coolant_temp_outlet_1` | ≤ 60 °C | 18–21 °C or 60–65 °C | < 18 °C or > 65 °C |
| `sensor:coolant_temp_outlet_2` | ≤ 60 °C | 18–21 °C or 60–65 °C | < 18 °C or > 65 °C |

## Delta Temperature (computed: outlet − inlet)

| Computed Key | Normal | Warning | Critical |
|---|---|---|---|
| `sensor:coolant_temp_inlet_1` − `sensor:coolant_temp_outlet_1` | ≤ 15 °C | 15–20 °C | > 20 °C |
| `sensor:coolant_temp_inlet_2` − `sensor:coolant_temp_outlet_2` | ≤ 15 °C | 15–20 °C | > 20 °C |

> Delta is calculated in the UI (not stored in Redis).
> Alarm: `alarm:coolant_delta_warning` / `alarm:coolant_delta_critical`

## Coolant Level

| Redis Keys | State | Level | Alarm |
|---|---|---|---|
| `sensor:water_level_high`=1, `sensor:water_level_low`=1 | HIGH | Normal | — |
| `sensor:water_level_high`=0, `sensor:water_level_low`=1 | MIDDLE | Warning | `alarm:water_level_warning` |
| `sensor:water_level_high`=0, `sensor:water_level_low`=0 | LOW | — | (undefined / future) |

## Coolant Leakage

| Redis Key | Value | Level | Alarm |
|---|---|---|---|
| `sensor:leak` | `NORMAL` | Normal | — |
| `sensor:leak` | `LEAKED` | Critical | `alarm:leak_detected` |

## Ambient (Chassis)

| Redis Key | Normal | Warning | Critical |
|---|---|---|---|
| `sensor:ambient_temp` | ≤ 40 °C | 40–50 °C | > 50 °C |
| `sensor:ambient_humidity` | 10–60 % | 60–80 % | < 10 % or > 80 % |

## Undetermined (TBD)

| Redis Key | Status |
|---|---|
| `sensor:ph` | Threshold not yet defined |
| `sensor:conductivity` | Threshold not yet defined |
| `sensor:flow_rate_1` / `_2` | Threshold not yet defined |
| `sensor:pressure` | Threshold not yet defined |

## Communication

| Redis Key | Value | Alarm |
|---|---|---|
| `comm:status` | `ok` | — |
| `comm:status` | `timeout` | `alarm:comm_timeout` |
| `comm:status` | `disconnected` | `alarm:comm_disconnected` |
