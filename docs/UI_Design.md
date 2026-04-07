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
| Top bar | 상단 | 시스템 상태 배지 (`OK` / `ALARM` / `COMM ERR`), 통신 상태, 현재 시각 |
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
│  [Monitoring] [History]   [ 1H ] [ 6H ] [ 24H ]   2024-01-01  │  ← Top bar
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   SENSOR TREND                                                   │
│   [ Inlet Temp ▾ ]                                              │  ← 메트릭 선택
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  (시계열 라인 차트)                                        │  │
│   │                                                           │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│   CONTROL HISTORY                                                │
│   timestamp          │ target │ value │ result                  │
│   2024-01-01 11:55  │ pump   │  60%  │ success                 │
│   2024-01-01 11:30  │ fan    │  40%  │ success                 │
│   (스크롤 가능)                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**패널 구성**

| 패널 | 내용 |
|---|---|
| Top bar | `← BACK` 버튼, 시간 범위 선택 (`1H` / `6H` / `24H`) |
| Sensor Trend | 메트릭 선택 드롭다운 + Prometheus 시계열 라인 차트 |
| Control History | 제어 명령 이력 테이블 (`timestamp`, `target`, `value`, `result`) |

---

## 2. Web UI (Svelte)

> 당분간 설계 보류. 구현 시점에 작성 예정.

**Environment**: 노트북/모니터 브라우저 — 1280px+ 가로, 마우스+키보드
**Reference**: `assets/UI example/ui layout 1~4.png`
