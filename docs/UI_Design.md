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
┌─────────────────────────────────────────────────────────────────┐
│  [Monitoring] [History]          ● OK          2024-01-01  12:00│  ← Top bar
├──────────────────────────────────────┬──────────────────────────┤
│                                      │                          │
│   COOLING HEALTH  (위치 미확정)       │   ACTIVE ALARMS          │
│                                      │                          │
│   [ Fan ]  [ Radiator ]              │  ⚠ coolant_temp_high    │
│                                      │  ⚠ comm_timeout         │
│   [ Reservoir ]  Level: NORMAL       │  ⚠ water_level_low      │
│                                      │                          │
│   [ Pump ]   status: ON              │  (스크롤 가능)            │
│                                      │                          │
│   [ Inlet Manifold ]                 ├──────────────────────────┤
│     Inlet Temp : 00.0 °C             │                          │
│     Flow       : 0.0 L/min           │   CONTROL                │
│     Pressure   : 0.00 bar            │                          │
│                                      │  Pump  [▼ -] [  0%] [+▲]│
│   [ Outlet Manifold ]                │  Fan   [▼ -] [  0%] [+▲]│
│     Outlet Temp: 00.0 °C             │                          │
│                                      │  [  APPLY  ]             │
│   [ Leak Sensor ]  Leak: NONE        │                          │
└──────────────────────────────────────┴──────────────────────────┘
```

**패널 구성**

| 패널 | 위치 | 내용 |
|---|---|---|
| Top bar | 상단 | 탭 네비 (`Monitoring` / `History`), 시스템 상태 배지 (`OK` / `ALARM` / `COMM ERR`), 통신 상태, 현재 시각 |
| Cooling Health | 좌측 메인 | CDU 흐름 다이어그램 — 부품 목록 아래 참고 |
| Active Alarms | 우상단 | `alarm:*` 활성 알람 목록 (스크롤), 없으면 "No active alarms" |
| Control | 우하단 | Pump / Fan 출력(%) 조절 버튼 + APPLY |

**Cooling Health 구성 요소** _(위치 미확정 — 추후 업데이트)_

| 구성 요소 | 표시 데이터 | Redis key |
|---|---|---|
| Fan | 팬 상태 | `sensor:fan_status` |
| Radiator | — | — |
| Reservoir | 수위 | `sensor:water_level` |
| Pump | 펌프 상태 | `sensor:pump_status` |
| Inlet Manifold | 입수 온도 | `sensor:coolant_temp_inlet` |
| Outlet Manifold | 출수 온도 | `sensor:coolant_temp_outlet` |
| Pipe / Flow | 유량, 유압 | `sensor:flow_rate`, `sensor:pressure` |
| Leak Sensor | 누수 감지 | `sensor:leak` |

**페이지 전환**: Top bar 우측에 `[HISTORY →]` 버튼 1개

---

### 1-2. History Page

```
┌─────────────────────────────────────────────────────────────────┐
│  [Monitoring] [History]          ● OK          2024-01-01  12:00│  ← Top bar (동일)
├──────────────────┬──────────────────────────────────────────────┤
│                  │                                               │
│  Time Range      │                                               │
│  [ 5m ▾ ]       │                                               │
│                  │                                               │
│  Graph Form      │                                               │
│  (●) Line Graph  │   (선택된 Graph Form에 맞게 렌더링)            │
│  ( ) Table       │                                               │
│                  │                                               │
│  Metric          │                                               │
│  [✓] temp_inlet  │                                               │
│  [✓] temp_outlet │                                               │
│  [ ] pressure    │                                               │
│  [ ] flow_rate   │                                               │
│  [ ] pump_status │                                               │
│  [ ] fan_status  │                                               │
│  [ ] ctrl_cmd    │                                               │
│  [ ] comm_event  │                                               │
│                  │                                               │
└──────────────────┴──────────────────────────────────────────────┘
```

**패널 구성**

| 패널 | 위치 | 내용 |
|---|---|---|
| Top bar | 상단 | Monitoring 페이지와 동일 — 탭 네비, 시스템 상태 배지, 현재 시각 |
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
