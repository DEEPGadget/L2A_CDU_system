# UI Design

> Layout reference images: `assets/UI example/`
> - `dg5r dashboard.png` — Local UI reference (Cooling Health panel + Alert List)
> - `ui layout 1~4.png` — Web UI reference (SCADA service UI)

---

## 1. Local UI (PySide6)

**Environment**: Raspberry Pi Touch Display 2 — 800×480, touch interaction
**Design principle**: Low information density, large touch targets, critical values only at a glance

---

### 1-1. Monitoring & Control Page

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  [Monitoring] [History]  ● System: Normal  ● Link: Normal  2024-01-01 12:00          │  ← Top bar
├──────────────────────────────────────────────────────────┬──────────────────────────┤
│                                                          │                          │
│   Cooling Health                                         │   Active Alarms          │
│                                                          │                          │
│   [Radiator] ←── [Fan1] [Fan2]                           │  ⚠ coolant_temp_high    │
│       │                                                  │  ⚠ comm_timeout         │
│   [Water Tank]                                           │  ⚠ water_level_low      │
│    Level: Normal                                         │                          │
│    pH   : 0.0                                            │  (스크롤 가능)            │
│    Cond : 0.0 μS/cm                                      │                          │
│       │                                                  ├──────────────────────────┤
│   [P1→P2] Loop1  [P3→P4] Loop2                           │                          │
│    Flow1: 0.0 L/min  Flow2: 0.0 L/min                    │   Control                │
│       │              │                                   │                          │
│   [Inlet Manifold]                                       │  Pump1 [▼ -] [  0%] [+▲]│
│    Loop1: 00.0°C  Loop2: 00.0°C                          │  Pump2 [▼ -] [  0%] [+▲]│
│       │  (Svr1) (Svr2) │                                 │  Fan1  [▼ -] [  0%] [+▲]│
│   [Outlet Manifold]                                      │  Fan2  [▼ -] [  0%] [+▲]│
│                                                          │  [  Apply  ]             │
│    Loop1: 00.0°C  Loop2: 00.0°C                          │                          │
│                                                          │  Leak : None             │
└──────────────────────────────────────────────────────────┴──────────────────────────┘
```

> **냉각수 흐름**: Water Tank → [P1·P2 → Server1] / [P3·P4 → Server2] → Inlet Manifold → Outlet Manifold → Radiator → Water Tank

**패널 구성**

| 패널 | 위치 | 내용 |
|---|---|---|
| Top bar | 상단 | 탭 네비 (`Monitoring` / `History`), **System 배지** (`Normal` / `Warning` / `Critical` / `-`) — 시스템 내부 상태(센서·알람), Link 통신 오류 시 `-` 표시, **Link 배지** (`Normal` / `Warning` / `Critical`) — Modbus 통신 상태, 현재 시각 |
| Cooling Health | 좌측 메인 | CDU 흐름 다이어그램 — Pub/Sub(`sensor:*`, `comm:*`) 수신 시 즉시 갱신, 부품 목록 아래 참고 |
| Active Alarms | 우상단 | `alarm:*` Keyspace Notification(SET/DEL) 수신 → 즉시 갱신, 없으면 "No active alarms" |
| Control | 우하단 | Pump1(Loop1) / Pump2(Loop2) / Fan1(Loop1) / Fan2(Loop2) 출력(%) 조절 버튼 + APPLY, Leak 상태 표시 |

**Cooling Health 구성 요소**

| 구성 요소 | 위치 | 표시 데이터 | Redis key |
|---|---|---|---|
| Radiator | 상단 | — | — |
| Fan Loop1 | 상단 | 팬 상태 (루프1) | `sensor:fan_status_1` |
| Fan Loop2 | 상단 | 팬 상태 (루프2) | `sensor:fan_status_2` |
| Water Tank | 상단 | 수위 / pH / 전도도 | `sensor:water_level_high`, `sensor:water_level_low`, `sensor:ph`, `sensor:conductivity` |
| Pump Loop1 (P1·P2 직렬) | 중단 | 펌프 상태 (루프1) | `sensor:pump_status_1` |
| Pump Loop2 (P3·P4 직렬) | 중단 | 펌프 상태 (루프2) | `sensor:pump_status_2` |
| Flow Loop1 | Pump ~ Manifold (루프1) | 유량 (루프1) | `sensor:flow_rate_1` |
| Flow Loop2 | Pump ~ Manifold (루프2) | 유량 (루프2) | `sensor:flow_rate_2` |
| Inlet Manifold | 중단 | 입수 온도 루프1·2 | `sensor:coolant_temp_inlet_1`, `sensor:coolant_temp_inlet_2` |
| Outlet Manifold | 하단 | 출수 온도 루프1·2 | `sensor:coolant_temp_outlet_1`, `sensor:coolant_temp_outlet_2` |
| Leak Sensor | 우하단 표시 | 누수 감지 | `sensor:leak` |
| Pressure | — | 유압 (부착 여부 미확정) | `sensor:pressure` |
| Ambient | — | 외기 온/습도 (부착 위치 미확정) — RPi I2C/GPIO 직접 수집 (Modbus 미경유) | `sensor:ambient_temp`, `sensor:ambient_humidity` |

**페이지 전환**: Top bar 탭 (`Monitoring` / `History`) 선택

---

### 1-2. History Page

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  [Monitoring] [History]  ● System: Normal  ● Link: Normal  2024-01-01 12:00          │  ← Top bar (동일)
├──────────────────┬──────────────────────────────────────────────────────────────────┤
│                  │                                                                  │
│  Time Range      │                                                                  │
│  [ 5m ▾ ]       │                                                                  │
│                  │                                                                  │
│  Graph Form      │                                                                  │
│  (●) Line Graph  │   (선택된 Graph Form에 맞게 렌더링)                              │
│  ( ) Table       │                                                                  │
│                  │                                                                  │
│  Metric          │                                                                  │
│  [✓] temp_inlet  │                                                                  │
│  [✓] temp_outlet │                                                                  │
│  [ ] pressure    │                                                                  │
│  [ ] flow_rate   │                                                                  │
│  [ ] pump_status │                                                                  │
│  [ ] fan_status  │                                                                  │
│  [ ] ctrl_cmd    │                                                                  │
│  [ ] comm_event  │                                                                  │
│                  │                                                                  │
└──────────────────┴──────────────────────────────────────────────────────────────────┘
```

**패널 구성**

| 패널 | 위치 | 내용 |
|---|---|---|
| Top bar | 상단 | Monitoring 페이지와 동일 — 탭 네비, System/Link 배지, 현재 시각 |
| Sidebar | 좌측 | Time Range 드롭다운 + Graph Form 라디오 버튼 + Metric 체크박스 |

> **Sidebar 드롭다운 동작**: 클릭 시 사이드바 위에 overlay(popup)로 표시. 레이아웃을 밀지 않음. PySide6 `QComboBox` 기본 popup 방식 사용.
| View area | 우측 메인 | 선택된 Graph Form에 따라 Line Graph or Table 렌더링 |

**Graph Form 옵션**

| 선택 | 렌더링 |
|---|---|
| Line Graph | 선택된 Metric을 시계열 꺾은선 그래프로 표시 |
| Table | 선택된 Metric을 timestamp 기준 테이블로 표시 |

**Metric 선택 항목**

| Metric | 데이터 소스 |
|---|---|
| `coolant_temp_inlet` | Prometheus Exporter |
| `coolant_temp_outlet` | Prometheus Exporter |
| `pressure` | Prometheus Exporter |
| `flow_rate` | Prometheus Exporter |
| `pump_status` | Prometheus Exporter |
| `fan_status` | Prometheus Exporter |
| `control_cmd` (pump / fan) | Prometheus Pushgateway |
| `comm_event` | Prometheus Pushgateway |

**시간 범위별 Prometheus 쿼리 step 기준** _(구현 시 확정)_

> 포인트 수를 고정(~60)하고 step을 범위에 맞게 조정 — 차트 밀도 일정 유지

| 범위 | step | 예상 포인트 수 |
|---|---|---|
| 5m | 5s | ~60 |
| 10m | 10s | ~60 |
| 30m | 30s | ~60 |
| 1H | 60s | ~60 |
| 6H | 6m | ~60 |
| 24H | 24m | ~60 |

---

## 2. Web UI (Svelte)

> 당분간 설계 보류. 구현 시점에 작성 예정.

**Environment**: 노트북/모니터 브라우저 — 1280px+ 가로, 마우스+키보드
**Reference**: `assets/UI example/ui layout 1~4.png`
