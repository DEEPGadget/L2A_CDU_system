# Sensor Thresholds

Alarm boundary values referenced by Redis key names.
Used as the source of truth for `src/fake_data/scenarios.py` and alarm manager logic.

## 업데이트 파이프라인

이 문서의 임계값을 수정할 경우 **반드시** 아래 파일도 함께 수정해야 합니다.

| 코드 파일 | 역할 |
|---|---|
| [`src/thresholds.py`](../src/thresholds.py) | **임계값 상수 유일 정의 위치** — 이 파일만 수정하면 됨 |
| [`src/local_ui/widgets/cooling_health.py`](../src/local_ui/widgets/cooling_health.py) | UI 색상 판정 (`src/thresholds.py` import) |
| [`src/fake_data/scenarios.py`](../src/fake_data/scenarios.py) | 시뮬레이터 drift 범위 (`src/thresholds.py` import) |

> threshold.md 수정 → `src/thresholds.py` 상수 수정 → 두 파일 자동 반영

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
| `sensor:water_level_high`=0, `sensor:water_level_low`=0 | LOW | Critical | `alarm:water_level_critical` |

## Coolant Leakage

| Redis Key | Value | UI 표시 | Level | Alarm |
|---|---|---|---|---|
| `sensor:leak` | `NORMAL` | `None` | Normal | — |
| `sensor:leak` | `LEAKED` | `Detected` | Critical | `alarm:leak_detected` |

## Ambient (Chassis)

| Redis Key | Normal | Warning | Critical |
|---|---|---|---|
| `sensor:ambient_temp` | ≤ 40 °C | 40–45 °C | > 45 °C |
| `sensor:ambient_humidity` | 8–60 % | 60–80 % | < 8 % or > 80 % |

## Chemistry (Warning only)

| Redis Key | Warning | Alarm Key |
|---|---|---|
| `sensor:ph` | < 7.8 | `alarm:ph_warning` |
| `sensor:conductivity` | < 4600 µs | `alarm:conductivity_warning` |

> Critical 없음. NVIDIA ALARM-REQ-17/18 기준 (preferred, not required).

## Undetermined (TBD)

| Redis Key | Status |
|---|---|
| `sensor:flow_rate_1` / `_2` | Threshold not yet defined |
| `sensor:pressure` | Threshold not yet defined |

## Communication

| Redis Key | Value | Alarm |
|---|---|---|
| `comm:status` | `ok` | — |
| `comm:status` | `timeout` | `alarm:comm_timeout` |
| `comm:status` | `disconnected` | `alarm:comm_disconnected` |
