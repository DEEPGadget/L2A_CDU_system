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

> Status strip 표시용 정보값. 알람 없음.
> 높은 ΔT는 서버 발열 증가를 의미하며 CDU 정상 동작 범위 내 현상임.
> 이상 감지는 outlet 절대 온도(`alarm:coolant_temp_l1/l2_critical`) 및 유량(`alarm:flow_rate_warning`)으로 판단.

| Computed Key | 표시 |
|---|---|
| `sensor:coolant_temp_outlet_1` − `sensor:coolant_temp_inlet_1` | ΔT1 (°C) — 색상 없음 |
| `sensor:coolant_temp_outlet_2` − `sensor:coolant_temp_inlet_2` | ΔT2 (°C) — 색상 없음 |

## Coolant Level

| `sensor:water_level` | State | Level | Alarm |
|---|---|---|---|
| `2` | HIGH | Normal | — |
| `1` | MIDDLE | Warning | `alarm:water_level_warning` |
| `0` | LOW | Critical | `alarm:water_level_critical` |

> MTM이 상위·하위 광센서 raw bit 조합으로 판단하여 `sensor:water_level` 단일 값으로 SET.
> raw: `high`=1, `low`=1 → `2` / `high`=0, `low`=1 → `1` / `high`=0, `low`=0 → `0` (`high`=1, `low`=0은 물리적으로 불가능)

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

| Redis Key | Normal | Warning | Alarm Key |
|---|---|---|---|
| `sensor:ph` | 8.0–10.5 | < 8.0 (alarm at < 7.8) | `alarm:ph_warning` |
| `sensor:conductivity` | ≥ 4600 µS/cm | < 4600 µS/cm | `alarm:conductivity_warning` |

> Normal pH range: GEN-REQ-08 (PG25 fluid spec 8.0–10.5).
> Alarm threshold: ALARM-REQ-17 (pH < 7.8), ALARM-REQ-18 (conductivity < 4600 µS/cm).
> Critical 없음 (preferred, not required).

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
