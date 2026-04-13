# UI Design

> Layout reference images: `assets/UI example/`
> - `dg5r dashboard.png` — Local UI reference (Cooling Health panel + Alert List)
> - `ui layout 1~4.png` — Web UI reference (SCADA service UI)

---

## 1. Local UI (PySide6)

**Environment**: Raspberry Pi Touch Display 2 — 1280×720 (landscape), touch interaction
**Design principle**: Low information density, large touch targets, critical values only at a glance

---

### 1-1. Monitoring & Control Page

**패널 구성**

| 패널 | 위치 | 내용 |
|---|---|---|
| Top bar | 상단 전체 | 탭 네비 (`Monitoring` / `History`), **System 배지** (`Normal` / `Warning` / `Critical` / `-`) — 시스템 내부 상태(센서·알람), Link 통신 오류 시 `-` 표시, **Link 배지** (`ok` / `timeout` / `disconnected`) — `comm:status` 값 그대로 표시, 현재 시각 |
| Cooling Health | 좌측 메인 (약 70%) | CDU 냉각수 흐름 다이어그램 — Pub/Sub(`sensor:*`, `comm:*`) 수신 시 즉시 갱신, 부품 목록 아래 참고 |
| Active Alarms | 우상단 | `alarm:*` Keyspace Notification(SET/DEL) 수신 → 즉시 갱신, 없으면 "No active alarms" (스크롤 가능) |
| Control | 우하단 | Pump/Fan PWM duty 설정 + Apply, Leak 상태 — 상세 아래 참고 |

**Control 패널 상세**

| 항목 | 표시 |
|---|---|
| Pump1 (Loop1) | 현재 PWM duty `XX%` — 터치 시 숫자 키패드 팝업 |
| Pump2 (Loop2) | 〃 |
| Fan1 (Loop1) | 〃 |
| Fan2 (Loop2) | 〃 |
| Leak | 상태 표시 (`None` / `Detected`) |
| **Apply** | 변경된 값을 MCG로 일괄 전송 |

> **조작 흐름**: 값 터치 → 숫자 키패드 팝업 (0–100, Range validation) → 입력 + Enter → 팝업 닫힘 → 필요 시 다른 장비도 변경 → **Apply** 터치 시 MCG로 전송.
> PySide6 구현: `QDialog` + `QGridLayout` 버튼 키패드.

**Cooling Health 구성 요소**

> **렌더링 방식**: SVG 템플릿 (`cooling_health.svg`) + `QSvgWidget`. 센서값 수신 시 플레이스홀더를 치환하여 리로드.
> **참고 이미지**: `assets/UI example/dg5r dashboard.png` (Cooling Health 패널), `assets/UI example/l2a cdu structure 1~3.png` (CDU 실물 구조)

> **냉각수 흐름**: Reservoir → Pump → (Flow Sensor) → Coolant Inlet Manifold → Server 1 / Server 2 → Coolant Outlet Manifold → Fan → Radiator → Reservoir (순환)

**다이어그램 배치 (위→아래)**

| 다이어그램 위치 | 구성 요소 | 표시 데이터 | Redis key |
|---|---|---|---|
| 최상단 | Reservoir (Water Tank) | Coolant Level, pH, 전도도 | `sensor:water_level_high`, `sensor:water_level_low`, `sensor:ph`, `sensor:conductivity` |
| ↓ | Pump Loop1 (P1·P2 직렬) / Pump Loop2 (P3·P4 직렬) | PWM duty (0–100 %) | `sensor:pump_pwm_duty_1`, `sensor:pump_pwm_duty_2` |
| ↓ (배관 중간) | Flow Loop1 / Flow Loop2 | 유량 | `sensor:flow_rate_1`, `sensor:flow_rate_2` |
| ↓ | Coolant Inlet Manifold | 입수 온도 루프1·2 | `sensor:coolant_temp_inlet_1`, `sensor:coolant_temp_inlet_2` |
| ↓ (좌·우 분기) | Server 1 / Server 2 | (열원 표시, 센서 없음) | — |
| ↓ (합류) | Coolant Outlet Manifold | 출수 온도 루프1·2 | `sensor:coolant_temp_outlet_1`, `sensor:coolant_temp_outlet_2` |
| ↓ | Fan Loop1 / Fan Loop2 | PWM duty (0–100 %) | `sensor:fan_pwm_duty_1`, `sensor:fan_pwm_duty_2` |
| 최하단 | Radiator | (표시만) | — |
| 다이어그램 하단 텍스트 | Coolant ΔT1 / ΔT2 | outlet − inlet 계산값 | (계산) |
| 다이어그램 하단 텍스트 | Leak Detection | 누수 감지 | `sensor:leak` |
| 다이어그램 하단 텍스트 | Ambient Temp / Humidity | 외기 온·습도 — RPi I2C/GPIO 직접 수집 (Modbus 미경유) | `sensor:ambient_temp`, `sensor:ambient_humidity` |
| 다이어그램 하단 텍스트 | Pressure | 유압 (부착 여부 미확정) | `sensor:pressure` |

**페이지 전환**: Top bar 탭 (`Monitoring` / `History`) 선택

---

### 1-2. History Page

**레이아웃 구조**

| 영역 | 위치 | 내용 |
|---|---|---|
| Top bar | 상단 | Monitoring 페이지와 동일 — 탭 네비, System/Link 배지, 현재 시각 |
| Sidebar | 좌측 (좁은 폭) | Time Range 드롭다운 + Graph Form 라디오 버튼 + Metric 체크박스 |
| View area | 우측 메인 | 선택된 Graph Form에 따라 Line Graph or Table 렌더링 |

> **Sidebar 드롭다운 동작**: 클릭 시 사이드바 위에 overlay(popup)로 표시. 레이아웃을 밀지 않음. PySide6 `QComboBox` 기본 popup 방식 사용.

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
| `pump_pwm_duty` | Prometheus Exporter |
| `fan_pwm_duty` | Prometheus Exporter |
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
