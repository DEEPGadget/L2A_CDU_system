# UI Design

> Layout reference images: `assets/UI example/`
> - `dg5r dashboard.png` — Local UI reference (Cooling Health panel + Alert List)
> - `ui layout 1~4.png` — Web UI reference (SCADA service UI)

---

## 1. Local UI (PySide6)

**Environment**: Raspberry Pi Touch Display 2 — 1280×720 (landscape), touch interaction

**Design principles**

| # | 원칙 |
|---|---|
| 1 | **흰 배경** — 전체 배경색 white (`#ffffff`) |
| 2 | **회색·흐릿한 글씨 금지** — 모든 텍스트는 충분한 명도 대비 확보, 비활성 표현은 색상 대신 레이아웃으로 |
| 3 | **상태값 색상 3종 통일 (global)** — Normal/OK `#27ae60` · Warning `#e67e22` · Critical `#e74c3c`. 상태가 없는 일반 값은 `#000000` (검정) |
| 4 | **Bold는 제목(heading) 및 상태값만** — 센서값·레이블 등은 regular weight. 예외: Top bar의 System·Link 상태값(Normal/Warning 등)은 bold + 색상으로 표현 (버튼·배지 형태 없이 텍스트만으로 상태 강조) |
| 5 | **배관 중앙 관통 원칙** — 냉각수 루프(배관 라인)는 각 컴포넌트 박스의 중앙을 관통하도록 렌더링. 컴포넌트는 배관이 지나가는 역(station)처럼 표현. 박스 좌측 엣지로 유입 → 박스 중앙에 값·레이블 표시 → 박스 우측 엣지로 유출. 컴포넌트 간 배관 세그먼트로 연결. (`assets/UI example/cooling health.svg.png` 참고) |
| 6 | **유로(배관) 색상** — 냉각수 온도 상태에 따라 구간별 색상 구분: 공급측(Reservoir→Pump→Flow→Inlet Manifold) 파랑 계열, 환수측(Outlet Manifold→Fan+Radiator) 빨강 계열. Server 박스에서 파랑→빨강 전환. 복귀 배관(Fan+Radiator 우단→Reservoir 좌단, 다이어그램 상/하단 테두리 경유)도 빨강→파랑 전환으로 표현. |
| 7 | **컴포넌트 경계선 색상** — 열적 역할에 따라 고정: Reservoir·Inlet Manifold = 파란 실선 border / Outlet Manifold = 빨간 실선 border / Pump·Fan+Radiator = 회색 실선 border (중립 기계 요소) / Server 1·2 = 회색 **점선** border (`stroke-dasharray`) — 중립색 + 점선으로 CDU 외부 장치임을 구분 |
| 8 | **컴포넌트 이름 배치** — 모든 컴포넌트 이름은 박스 내부 상단에 표시 (bold). 박스 내부 구성: 이름(상단) → 값(중앙) → 단위(하단). 레인 좌측에 "L1" / "L2" 행 레이블로 루프 구분. |
| 12 | **최소 글자 크기** — 모든 텍스트(다이어그램·팝업·버튼 포함)는 최소 20px. 값(센서·PWM)은 24px 이상. 그 이하 크기 사용 금지. (HMI 터치 환경 기준) |
| 9 | **Server 외부 분기 표현** — Inlet Manifold에서 차가운 냉각수가 서버로 나갔다가 뜨거워져 Outlet Manifold로 돌아오는 흐름을 수직 분기로 표현. Loop 1의 서버는 레인 위쪽으로, Loop 2의 서버는 레인 아래쪽으로 분기. Inlet→Server→Outlet 은 하나의 연결된 유로. |
| 10 | **Reservoir 구조** — Reservoir 박스는 두 레인(Loop 1·2) 높이 전체를 커버하는 단일 박스. 박스 상단→Loop 1 배관, 박스 하단→Loop 2 배관으로 분기. 내부에 이름·레벨 바·상태 텍스트 표시. |
| 11 | **Status strip** — ΔT1·ΔT2·Leak·Ambient·Pressure는 SVG 아래 별도 QWidget으로 배치. SVG는 다이어그램만 담당, status strip은 Python에서 직접 갱신. |

---

### 1-1. Monitoring & Control Page

**레이아웃 개요**

```
┌────────────────────────────────────────────────────────────────────────────┐
│ [Monitoring] [History] │ 🔔N  IP:x.x.x.x  System:Warning  Link:ok │ 12:34:56│  52px
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│                   Cooling Health (SVG, 전체 1280px 폭)                    │  ~608px
│       센서값 색상 코딩 — 정상 green / 경고 orange / 위급 red              │
│       Pump·Fan 노드: 탭 가능 (✎) → 숫자 키패드 팝업                      │
│                                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│  ΔT1:__°C  ΔT2:__°C  Leak:None  Ambient:__°C/__% RH  Pressure:__ bar     │  ~60px
└────────────────────────────────────────────────────────────────────────────┘
```

**패널 구성**

| 패널 | 위치 | 내용 |
|---|---|---|
| Top bar | 상단 전체 | 탭 네비 (`Monitoring` / `History`), **알람 배지** (`🔔 N` — 알람 없을 때 숨김, 탭 시 floating overlay), `IP: x.x.x.x`, `System: Normal/Warning/Critical/-`, `Link: ok/timeout/disconnected`, 현재 시각 `HH:MM:SS` |
| Cooling Health | top bar 아래 ~ status strip 위 | CDU 냉각수 흐름 SVG 다이어그램 **전체 폭 (1280px)** — Pub/Sub(`sensor:*`, `comm:*`) 수신 시 즉시 갱신, Pump·Fan 노드는 탭으로 직접 제어 가능, 부품 목록 아래 참고 |
| Status strip | 최하단 고정 (별도 QWidget) | ΔT1·ΔT2·Leak·Ambient Temp/Humidity·Pressure — 텍스트 나열, 1초 갱신 |

**Top bar 레이아웃**

| 영역 | 항목 | 스타일 |
|---|---|---|
| 좌측 | `Monitoring` / `History` 탭 버튼 | 현재보다 크게, 활성 탭 강조. 버튼 형태 유지 (탭 전환 인터랙션 있음) |
| 중앙 (flex 확장) | 알람 배지, IP, System 상태, Link 상태 | 수평 중앙 정렬 |
| 우측 | `HH:MM:SS` | 우측 고정, 1초 갱신 |

**Top bar 항목 상세**

| 항목 | 형식 | 비고 |
|---|---|---|
| 탭 버튼 | `Monitoring` `History` | 좌측 배치. 활성 탭 강조, 비활성은 일반 |
| 알람 배지 | `🔔 N` | 중앙. 알람 없을 때 숨김, Warning=주황 / Critical=빨강, 탭 시 overlay |
| IP | `IP: 192.168.x.x` | 중앙. 유선 우선, 없으면 `IP: --` |
| System | `System:` + **상태값(bold, 색상)** | 중앙. 버튼·배지 형태 없음 — bold 컬러 텍스트만. Normal=green / Warning=orange / Critical=red / `-`=black |
| Link | `Link:` + **상태값(bold, 색상)** | 중앙. 버튼·배지 형태 없음 — bold 컬러 텍스트만. ok=green / timeout=orange / disconnected=red |
| 시각 | `HH:MM:SS` | 우측 고정, 1초 갱신 |

**알람 배지 상세**

| 상태 | 표시 |
|---|---|
| 알람 없음 | 배지 숨김 |
| Warning 1개 이상 (Critical 없음) | `🔔 N` (주황) |
| Critical 1개 이상 | `🔔 N` (빨강) — Warning 동시 존재 시 Critical 우선 |
| 배지 탭 | 배지 위치 기준 floating overlay로 알람 목록 펼침 (스크롤 가능, ✕ 또는 영역 밖 탭으로 닫기) |
| 알람 전부 해소 | overlay auto-close + 배지 숨김 |

**Pump·Fan 인라인 제어**

| 항목 | SVG 내 표시 | 동작 |
|---|---|---|
| Pump Loop1 | PWM duty `XX% ✎` | 탭 → 숫자 키패드 팝업 → **Apply** → MCG 전송 (real mode) / Redis 직접 쓰기 (fake mode) |
| Pump Loop2 | 〃 | 〃 |
| Fan Loop1 | 〃 | 〃 |
| Fan Loop2 | 〃 | 〃 |

> **조작 흐름**: 다이어그램 내 Pump/Fan 노드 탭 (✎ 표시로 편집 가능 인지) → 숫자 키패드 팝업 (0–100, Range validation) → 입력 후 **Apply** → MCG 전송 (real mode) / Redis 직접 쓰기 (fake mode) → SVG 값 갱신.
> PySide6 구현: `QSvgWidget` 위에 투명 `QPushButton` 오버레이 (절대 위치), 팝업은 `QDialog` + `QGridLayout` 키패드.

**Cooling Health 구성 요소**

> **렌더링 방식**: SVG 템플릿 (`cooling_health.svg`) + `QSvgWidget`. 센서값 수신 시 플레이스홀더를 치환하여 리로드.
> **참고 이미지**: `assets/UI example/dg5r dashboard.png` (Cooling Health 패널), `assets/UI example/l2a cdu structure 1~3.png` (CDU 실물 구조)

> **냉각수 흐름** (루프별 독립): Reservoir → Pump → Flow → Inlet Manifold → Server → Outlet Manifold → Fan+Radiator → Reservoir (순환)
> Loop 1 → Server 1, Loop 2 → Server 2 각 1:1 독립 연결. Reservoir는 CDU 내부 공유, Fan+Radiator는 루프별 독립.

**다이어그램 배치 (좌→우, 2-lane)**

| 레인 | 구성 요소 | 표시 데이터 | Redis key |
|---|---|---|---|
| 공유 (좌단) | Reservoir (Water Tank) | Coolant Level (레벨 바 + HIGH/MID/LOW 텍스트), pH, 전도도 (µS/cm) | `sensor:water_level_high`, `sensor:water_level_low`, `sensor:ph`, `sensor:conductivity` |
| Loop 1 → | Pump Loop1 (P1·P2 직렬) | PWM duty (0–100 %) ✎ | `sensor:pump_pwm_duty_1` |
| Loop 1 → | Flow Loop1 | 유량 (L/min) | `sensor:flow_rate_1` |
| Loop 1 → | Coolant Inlet Manifold L1 | 입수 온도 (°C) | `sensor:coolant_temp_inlet_1` |
| Loop 1 ↑ 분기 | Server 1 | (열원 표시, 센서 없음, CDU 외부 — 위로 분기) | — |
| Loop 1 → | Coolant Outlet Manifold L1 | 출수 온도 (°C) | `sensor:coolant_temp_outlet_1` |
| Loop 1 → | Fan1 + Radiator | PWM duty (0–100 %) ✎ | `sensor:fan_pwm_duty_1` |
| Loop 2 → | Pump Loop2 (P3·P4 직렬) | PWM duty (0–100 %) ✎ | `sensor:pump_pwm_duty_2` |
| Loop 2 → | Flow Loop2 | 유량 (L/min) | `sensor:flow_rate_2` |
| Loop 2 → | Coolant Inlet Manifold L2 | 입수 온도 (°C) | `sensor:coolant_temp_inlet_2` |
| Loop 2 ↓ 분기 | Server 2 | (열원 표시, 센서 없음, CDU 외부 — 아래로 분기) | — |
| Loop 2 → | Coolant Outlet Manifold L2 | 출수 온도 (°C) | `sensor:coolant_temp_outlet_2` |
| Loop 2 → | Fan2 + Radiator | PWM duty (0–100 %) ✎ | `sensor:fan_pwm_duty_2` |

**Status strip 항목 (SVG 아래 별도 QWidget)**

| 항목 | 표시 데이터 | Redis key |
|---|---|---|
| Coolant ΔT1 / ΔT2 | outlet − inlet 계산값 (°C), 색상 코딩 적용 — ≤15°C=green / 15–20°C=orange / >20°C=red | (계산) |
| Leak Detection | `None` (green) / `Detected` (red) | `sensor:leak` |
| Ambient Temp / Humidity | 외기 온·습도 (°C / % RH) — RPi I2C/GPIO 직접 수집 (Modbus 미경유) | `sensor:ambient_temp`, `sensor:ambient_humidity` |
| Pressure | 유압 (bar, 부착 여부 미확정) | `sensor:pressure` |

**페이지 전환**: Top bar 탭 (`Monitoring` / `History`) 선택

---

### 1-2. History Page

**레이아웃 구조**

| 영역 | 위치 | 내용 |
|---|---|---|
| Top bar | 상단 | Monitoring 페이지와 동일 — 탭 네비, 알람 배지, System/Link 상태 텍스트, 현재 시각 |
| Sidebar | 좌측 고정 폭 (320px) | Time Range 드롭다운 + Graph Form 라디오 버튼 + Metric 그룹 (접이식) |
| View area | 우측 메인 | 선택된 Metric에 따라 Line Chart / State Timeline / Table 렌더링 |

> **Sidebar 드롭다운 동작**: 클릭 시 사이드바 위에 overlay(popup)로 표시. 레이아웃을 밀지 않음. PySide6 `QComboBox` 기본 popup 방식 사용.

---

**시간 범위 (Time Range)**

`step = max(range_seconds / 60, 1)` — 포인트 수 ~60 고정

| 범위 | step | 예상 포인트 |
|---|---|---|
| 5m  | 5s  | ~60 |
| 10m | 10s | ~60 |
| 30m | 30s | ~60 |
| 1H  | 60s | ~60 |
| 6H  | 6m  | ~60 |
| 24H | 24m | ~60 |

---

**Graph Form 라디오**

| 선택 | 연속형 수치 metric | 이진/이산 metric (Leak·Comm Events) | 이벤트 로그 metric (Alarm History·Control Cmd) |
|---|---|---|---|
| Line Graph | Line Chart 렌더링 | **State Timeline** 고정 (라디오 무관) | **Table** 고정 (라디오 무관) |
| Table | Table 렌더링 | Table 렌더링 | Table 렌더링 |

---

**Metric 그룹 (Sidebar — 접이식)**

그룹 헤더 탭 → 펼침/접힘 토글. 기본 접힘. 각 항목은 개별 체크박스.

```
▶ Coolant Temp
    ☐ Inlet  L1    ☐ Inlet  L2
    ☐ Outlet L1    ☐ Outlet L2
▶ Coolant Quality
    ☐ pH
    ☐ Conductivity
    ☐ Water Level
▶ Flow & Pressure
    ☐ Flow Rate L1    ☐ Flow Rate L2
    ☐ Pressure
▶ PWM Duty
    ☐ Pump Duty L1    ☐ Pump Duty L2
    ☐ Fan Duty L1     ☐ Fan Duty L2
▶ Environment
    ☐ Ambient Temp
    ☐ Ambient Humidity
▶ Events
    ☐ Leak              (State Timeline / Table)
    ☐ Comm Events       (State Timeline / Table)
    ☐ Alarm History     (Table only — 발생/해제 이벤트 기록)
    ☐ Control Cmd – Pump  (Table only)
    ☐ Control Cmd – Fan   (Table only)
    ☐ Comm Failures     (Line / Table)
```

**체크박스 ↔ Prometheus 메트릭 매핑**

| 체크박스 | Prometheus 쿼리 | 단위 | 렌더링 |
|---|---|---|---|
| Inlet L1 | `sensor_coolant_temp_inlet{loop="1"}` | °C | Line / Table |
| Inlet L2 | `sensor_coolant_temp_inlet{loop="2"}` | °C | Line / Table |
| Outlet L1 | `sensor_coolant_temp_outlet{loop="1"}` | °C | Line / Table |
| Outlet L2 | `sensor_coolant_temp_outlet{loop="2"}` | °C | Line / Table |
| Flow Rate L1 | `sensor_flow_rate{loop="1"}` | L/min | Line / Table |
| Flow Rate L2 | `sensor_flow_rate{loop="2"}` | L/min | Line / Table |
| Pressure | `sensor_pressure` | bar | Line / Table |
| Pump Duty L1 | `sensor_pump_pwm_duty{loop="1"}` | % | Line / Table |
| Pump Duty L2 | `sensor_pump_pwm_duty{loop="2"}` | % | Line / Table |
| Fan Duty L1 | `sensor_fan_pwm_duty{loop="1"}` | % | Line / Table |
| Fan Duty L2 | `sensor_fan_pwm_duty{loop="2"}` | % | Line / Table |
| pH | `sensor_ph` | — | Line / Table |
| Conductivity | `sensor_conductivity` | µS/cm | Line / Table |
| Water Level | `sensor_water_level` | — | **State Timeline** / Table |
| Ambient Temp | `sensor_ambient_temp` | °C | Line / Table |
| Ambient Humidity | `sensor_ambient_humidity` | % RH | Line / Table |
| Leak | `sensor_leak` | — | **State Timeline** / Table |
| Comm Events | `comm_event` | — | **State Timeline** / Table |
| Alarm History | `alarm_state{alarm=~".+"}` | — | **Table only** |
| Control Cmd – Pump | `control_cmd_pump` | — | **Table only** |
| Control Cmd – Fan | `control_cmd_fan` | — | **Table only** |
| Comm Failures | `comm_consecutive_failures` | count | Line / Table |

---

**차트 배치 규칙 (Grafana 스타일)**

같은 그룹에서 여러 항목을 선택하면 **단위가 같은 항목은 하나의 차트에 다중 시리즈로 합침**. 단위가 다른 항목은 별도 차트로 분리. 차트는 View area에 수직으로 쌓임.

| 그룹 | 차트 구성 예 |
|---|---|
| Coolant Temp | Inlet·Outlet 모두 선택 → 차트 1개 (전부 °C) — ΔT 시각적 확인 |
| Hydraulics | Flow Rate → 차트①, Pressure → 차트② (단위 다름) |
| PWM Duty | Pump·Fan 모두 선택 → 차트 1개 (전부 %) |
| Coolant Quality | pH → 차트①, Conductivity → 차트②, Water Level → 차트③ |
| Environment | Ambient Temp → 차트①, Ambient Humidity → 차트② |
| Events | Table / State Timeline — 차트 없음 |

**차트 제목**: `{그룹명} — {선택 항목 나열}` (예: `Coolant Temp — Inlet L1, Outlet L1`)

**Multi-series 색상·범례**

| 규칙 | 값 |
|---|---|
| L1 계열 색상 | `#2980b9` (파랑) |
| L2 계열 색상 | `#e67e22` (주황) |
| 같은 루프 내 항목 구분 | Inlet = 실선, Outlet = 점선 |

범례 레이블: 체크박스 레이블과 동일 (`Inlet L1`, `Outlet L2` 등)

---

**State Timeline 위젯**

> 구현 파일: `src/local_ui/widgets/state_timeline.py` — `StateTimelineWidget(QWidget)` (step 2에서 신규 작성)
> pyqtgraph 미설치 환경 — PySide6 `QPainter` 로만 구현

- X축 = 시간 (선택된 Time Range), Y축 = 각 metric 행(row)
- 각 시간 구간을 상태 색상 블록으로 채움
- 상태 색상: Normal `#27ae60` · Warning `#e67e22` · Critical `#e74c3c` · Unknown `#bdc3c7`
- 행 좌측에 metric 레이블, X축 하단에 시간 눈금

**이진/이산 상태 매핑**

| metric | 값 | 상태 레이블 | 색상 |
|---|---|---|---|
| `sensor_water_level` | 2 | HIGH | `#27ae60` |
| | 1 | MIDDLE | `#e67e22` |
| | 0 | LOW | `#e74c3c` |
| `sensor_leak` | 0 | NORMAL | `#27ae60` |
| | 1 | LEAKED | `#e74c3c` |
| `comm_event` | ok | ok | `#27ae60` |
| | timeout | timeout | `#e67e22` |
| | disconnected | disconnected | `#e74c3c` |

---

**Table 컬럼 상세**

| metric 종류 | 컬럼 구성 |
|---|---|
| 연속형·카운터 (단일) | Timestamp \| Value |
| 연속형·카운터 (L1+L2) | Timestamp \| L1 Value \| L2 Value |
| State Timeline (Table 모드: Leak·Comm Events) | Timestamp \| Status |
| Alarm History | Timestamp \| Alarm \| Level (`warning`/`critical`) \| Event (`active`/`resolved`) |
| Control Cmd Pump/Fan | Timestamp \| Value (%) \| Result (`success`/`fail`) |

---

**Prometheus 메트릭 네이밍 (Exporter 설계 기준)**

Exporter가 Redis `sensor:*` + `alarm:*` 를 읽어 아래 이름으로 expose:

```
# 센서값 (sensor:* → Exporter Pull)
sensor_coolant_temp_inlet{loop="1"}    ← sensor:coolant_temp_inlet_1
sensor_coolant_temp_inlet{loop="2"}    ← sensor:coolant_temp_inlet_2
sensor_coolant_temp_outlet{loop="1"}   ← sensor:coolant_temp_outlet_1
sensor_coolant_temp_outlet{loop="2"}   ← sensor:coolant_temp_outlet_2
sensor_flow_rate{loop="1"}             ← sensor:flow_rate_1
sensor_flow_rate{loop="2"}             ← sensor:flow_rate_2
sensor_pressure                        ← sensor:pressure
sensor_pump_pwm_duty{loop="1"}         ← sensor:pump_pwm_duty_1
sensor_pump_pwm_duty{loop="2"}         ← sensor:pump_pwm_duty_2
sensor_fan_pwm_duty{loop="1"}          ← sensor:fan_pwm_duty_1
sensor_fan_pwm_duty{loop="2"}          ← sensor:fan_pwm_duty_2
sensor_ph                              ← sensor:ph
sensor_conductivity                    ← sensor:conductivity
sensor_water_level                     ← 파생: high:1 low:1→2 / high:0 low:1→1 / low:0→0
sensor_leak                            ← sensor:leak  (NORMAL→0, LEAKED→1)
sensor_ambient_temp                    ← sensor:ambient_temp
sensor_ambient_humidity                ← sensor:ambient_humidity

# 알람 상태 이력 (alarm:* → Exporter Pull)
alarm_state{alarm="coolant_temp_l1_warning"}    ← alarm:coolant_temp_l1_warning  (키 있음=1, 없음=0)
alarm_state{alarm="coolant_temp_l1_critical"}   ← alarm:coolant_temp_l1_critical (키 있음=2, 없음=0)
alarm_state{alarm="coolant_temp_l2_warning"}
alarm_state{alarm="coolant_temp_l2_critical"}
alarm_state{alarm="leak_detected"}              ← (있음=2, 없음=0)
alarm_state{alarm="water_level_warning"}        ← (있음=1, 없음=0)
alarm_state{alarm="water_level_critical"}       ← (있음=2, 없음=0)
alarm_state{alarm="ph_warning"}
alarm_state{alarm="conductivity_warning"}
alarm_state{alarm="flow_rate_warning"}
alarm_state{alarm="pressure_warning"}
alarm_state{alarm="ambient_temp_warning"}
alarm_state{alarm="ambient_temp_critical"}
alarm_state{alarm="ambient_humidity_warning"}
alarm_state{alarm="ambient_humidity_critical"}
alarm_state{alarm="comm_timeout"}               ← (있음=1, 없음=0)
alarm_state{alarm="comm_disconnected"}          ← (있음=2, 없음=0)
# 값 규칙: 키 이름 suffix _warning → 1, _critical 또는 _detected/_disconnected → 2

# 이벤트/명령 이력 (Pushgateway — MCG Push)
control_cmd_pump{result="success|fail"}
control_cmd_fan{result="success|fail"}
comm_event{status="timeout|disconnected|ok"}
comm_consecutive_failures
```

---

## 2. Web UI (Svelte)

> 당분간 설계 보류. 구현 시점에 작성 예정.

**Environment**: 노트북/모니터 브라우저 — 1280px+ 가로, 마우스+키보드
**Reference**: `assets/UI example/ui layout 1~4.png`
