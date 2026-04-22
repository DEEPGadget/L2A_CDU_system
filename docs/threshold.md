# Sensor Thresholds

센서별 Normal / Warning / Critical 임계값 정의.

코드 반영: `src/thresholds.py` — 이 파일의 상수를 수정하면 UI 색상 판정(`cooling_health.py`)과 시뮬레이터(`scenarios.py`)에 자동 반영.

---

## Coolant Temperature

| 센서 | Redis Key | Normal | Warning | Critical |
|---|---|---|---|---|
| Inlet L1 | `sensor:coolant_temp_inlet_1` | 22–40 °C | 18–21 °C or 41–45 °C | < 18 °C or > 45 °C |
| Inlet L2 | `sensor:coolant_temp_inlet_2` | 22–40 °C | 18–21 °C or 41–45 °C | < 18 °C or > 45 °C |
| Outlet L1 | `sensor:coolant_temp_outlet_1` | ≤ 60 °C | 60–65 °C | > 65 °C |
| Outlet L2 | `sensor:coolant_temp_outlet_2` | ≤ 60 °C | 60–65 °C | > 65 °C |

## Delta Temperature (outlet − inlet)

| 센서 | Redis Key | Normal | Warning | Critical |
|---|---|---|---|---|
| ΔT1 | (계산값) | 정보 표시용 | — | — |
| ΔT2 | (계산값) | 정보 표시용 | — | — |

## Coolant Level

고/저 2개 레벨 센서로 수위 판단.

| 센서 | Redis Key | Normal | Warning | Critical |
|---|---|---|---|---|
| 수위 | `sensor:water_level` | HIGH (2) | MIDDLE (1) | LOW (0) |

## Leak Detection

| 센서 | Redis Key | Normal | Warning | Critical |
|---|---|---|---|---|
| 누수 | `sensor:leak` | NORMAL | — | LEAKED |

## Ambient (장치 내부)

| 센서 | Redis Key | Normal | Warning | Critical |
|---|---|---|---|---|
| 온도 | `sensor:ambient_temp` | ≤ 40 °C | 40–45 °C | > 45 °C |
| 습도 | `sensor:ambient_humidity` | 8–60 % | 60–80 % | < 8 % or > 80 % |

## Chemistry

| 센서 | Redis Key | Normal | Warning | Critical |
|---|---|---|---|---|
| pH | `sensor:ph` | 8.0–10.5 | < 7.8 | — |
| 전도도 | `sensor:conductivity` | ≥ 4600 µS/cm | < 4600 µS/cm | — |

## Flow / Pressure (TBD)

| 센서 | Redis Key | Normal | Warning | Critical |
|---|---|---|---|---|
| 유량 L1 | `sensor:flow_rate_1` | 미정 | 미정 | 미정 |
| 유량 L2 | `sensor:flow_rate_2` | 미정 | 미정 | 미정 |
| 유압 | `sensor:pressure` | 미정 | 미정 | 미정 |

## Communication

| 센서 | Redis Key | Normal | Warning | Critical |
|---|---|---|---|---|
| 통신 상태 | `comm:status` | ok | timeout | disconnected |
