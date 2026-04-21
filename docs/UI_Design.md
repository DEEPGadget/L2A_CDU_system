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
| 3 | **상태값 색상 3종 통일 (global)** — Normal/OK `#27ae60` · Warning `#e67e22` · Critical `#e74c3c`. 상태가 없는 일반 값은 `#000000` (검정). **History 차트 라인 색상은 상태색과 겹치지 않는 별도 팔레트를 사용** (아래 "History 시리즈 팔레트" 참고). 예외: Coolant Level 등 **의미 자체가 상태인** State Timeline 블록은 상태색 그대로 사용 (HIGH=green, MIDDLE=orange, LOW=red). |
| 4 | **Bold는 제목(heading) 및 상태값만** — 센서값·레이블 등은 regular weight. 예외: Top bar의 System·Link 상태값(Normal/Warning 등)은 bold + 색상으로 표현 (버튼·배지 형태 없이 텍스트만으로 상태 강조) |
| 5 | **배관 중앙 관통 원칙** — 냉각수 루프(배관 라인)는 각 컴포넌트 박스의 중앙을 관통하도록 렌더링. 컴포넌트는 배관이 지나가는 역(station)처럼 표현. 박스 좌측 엣지로 유입 → 박스 중앙에 값·레이블 표시 → 박스 우측 엣지로 유출. 컴포넌트 간 배관 세그먼트로 연결. (`assets/UI example/cooling health.svg.png` 참고) |
| 6 | **유로(배관) 색상** — 냉각수 온도 상태에 따라 구간별 색상 구분: 공급측(Reservoir→Pump→Flow→Inlet Manifold) 파랑 계열, 환수측(Outlet Manifold→Fan+Radiator) 빨강 계열. Server 박스에서 파랑→빨강 전환. 복귀 배관(Fan+Radiator 우단→Reservoir 좌단, 다이어그램 상/하단 테두리 경유)도 빨강→파랑 전환으로 표현. |
| 7 | **컴포넌트 경계선 색상** — 열적 역할에 따라 고정: Reservoir·Inlet Manifold = 파란 실선 border / Outlet Manifold = 빨간 실선 border / Pump·Fan+Radiator = 회색 실선 border (중립 기계 요소) / Server 1·2 = 회색 **점선** border (`stroke-dasharray`) — 중립색 + 점선으로 CDU 외부 장치임을 구분 |
| 8 | **컴포넌트 이름 배치** — 모든 컴포넌트 이름은 박스 내부 상단에 표시 (bold). 박스 내부 구성: 이름(상단) → 값(중앙) → 단위(하단). 레인 좌측에 "L1" / "L2" 행 레이블로 루프 구분. |
| 9 | **Server 외부 분기 표현** — Inlet Manifold에서 차가운 냉각수가 서버로 나갔다가 뜨거워져 Outlet Manifold로 돌아오는 흐름을 수직 분기로 표현. Loop 1의 서버는 레인 위쪽으로, Loop 2의 서버는 레인 아래쪽으로 분기. Inlet→Server→Outlet 은 하나의 연결된 유로. |
| 10 | **Reservoir 구조** — Reservoir 박스는 두 레인(Loop 1·2) 높이 전체를 커버하는 단일 박스. 박스 상단→Loop 1 배관, 박스 하단→Loop 2 배관으로 분기. 내부에 이름·레벨 바·상태 텍스트 표시. |
| 11 | **Status strip** — ΔT1·ΔT2·Leak·Ambient·Pressure는 SVG 아래 별도 QWidget으로 배치. SVG는 다이어그램만 담당, status strip은 Python에서 직접 갱신. |
| 12 | **최소 글자 크기** — 모든 텍스트(다이어그램·팝업·버튼·차트 axis/tick/legend·Table 셀 포함)는 최소 20px. 값(센서·PWM)은 24px 이상. 그 이하 크기 사용 금지. **근거**: 1) 터치 대상 영역은 손가락 조작이 편해야 함 2) 정보 표시도 1m 거리에서 읽혀야 함. pyqtgraph/QTableWidget 기본 폰트(9~11pt)는 명시적으로 재설정 필요. |

---

### 1-1. Monitoring & Control Page

**레이아웃 개요**

상단부터 수직 3단 (위→아래): **Top bar → Cooling Health SVG (전체 1280px 폭) → Status strip**. 높이는 위젯 콘텐츠에 맞춰 자연 결정 (Top bar는 코드에서 `setFixedHeight`, Status strip은 텍스트 1행). 픽셀 치수는 구현 파일 기준.

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
| Mode | `[Manual]` / `[Auto]` 토글 버튼 | 중앙, Link 우측에 배치. 탭하면 모드 전환 요청. 아래 "Mode 토글 버튼 상세" 참고 |
| 시각 | `HH:MM:SS` | 우측 고정, 1초 갱신 |

**Mode 토글 버튼 상세**

| 상태 | 텍스트 | 스타일 |
|---|---|---|
| Manual (기본) | `Manual` | 흰 배경 + `#2c3e50` 테두리/글자 (20px bold) |
| Auto (활성) | `Auto` | `#3498db` 파랑 배경 + 흰 글자 (20px bold) |

| 동작 | 설명 |
|---|---|
| 탭 시 | MCG에 모드 전환 요청 전송 (real mode: IPC / fake mode: Redis `control:mode` 직접 write) |
| 응답 | MCG 응답 후 Redis `control:mode` 변경 → Pub/Sub → UI 갱신 |
| 전환 중 | 버튼 일시 비활성화 (더블 탭 방지) |
| 비상정지 | Auto 모드 중 비상정지 시 자동으로 Manual 복귀 |

**알람 배지 상세**

| 상태 | 표시 |
|---|---|
| 알람 없음 | 배지 숨김 |
| Warning 1개 이상 (Critical 없음) | `🔔 N` (주황) |
| Critical 1개 이상 | `🔔 N` (빨강) — Warning 동시 존재 시 Critical 우선 |
| 배지 탭 | 배지 위치 기준 floating overlay로 알람 목록 펼침 (스크롤 가능, ✕ 또는 영역 밖 탭으로 닫기) |
| 알람 전부 해소 | overlay auto-close + 배지 숨김 |

**Pump·Fan 인라인 제어**

| 항목 | SVG 내 표시 (Manual) | SVG 내 표시 (Auto) | 동작 (Manual) | 동작 (Auto) |
|---|---|---|---|---|
| Pump Loop1 | PWM duty `XX% ✎` | PWM duty `XX%` (✎ 숨김) | 탭 → 숫자 키패드 팝업 → **Apply** | **비활성** — 탭 무반응 |
| Pump Loop2 | 〃 | 〃 | 〃 | 〃 |
| Fan Loop1 | 〃 | 〃 | 〃 | 〃 |
| Fan Loop2 | 〃 | 〃 | 〃 | 〃 |

> **Manual 모드 조작 흐름**: 다이어그램 내 Pump/Fan 노드 탭 (✎ 표시로 편집 가능 인지) → 숫자 키패드 팝업 (0–100, Range validation) → 입력 후 **Apply** → MCG 전송 (real mode) / Redis 직접 쓰기 (fake mode) → SVG 값 갱신.
> PySide6 구현: `QSvgWidget` 위에 투명 `QPushButton` 오버레이 (절대 위치), 팝업은 `QDialog` + `QGridLayout` 키패드.
>
> **Auto 모드**: 오버레이 버튼 비활성 (투명도 50%, 커서 기본), ✎ 아이콘 숨김. PWM 값은 MCG가 자동 계산한 값이 실시간 표시됨 (읽기 전용). 수동 제어하려면 Manual 모드로 전환 필요.

**Cooling Health 구성 요소**

> **렌더링 방식**: SVG 템플릿 (`cooling_health.svg`) + `QSvgWidget`. 센서값 수신 시 플레이스홀더를 치환하여 리로드.
> **참고 이미지**: `assets/UI example/dg5r dashboard.png` (Cooling Health 패널), `assets/UI example/l2a cdu structure 1~3.png` (CDU 실물 구조)

> **냉각수 흐름** (루프별 독립): Reservoir → Pump → Flow → Inlet Manifold → Server → Outlet Manifold → Fan+Radiator → Reservoir (순환)
> Loop 1 → Server 1, Loop 2 → Server 2 각 1:1 독립 연결. Reservoir는 CDU 내부 공유, Fan+Radiator는 루프별 독립.

**다이어그램 배치 (좌→우, 2-lane)**

| 레인 | 구성 요소 | 표시 데이터 | Redis key |
|---|---|---|---|
| 공유 (좌단) | Reservoir (Water Tank) | Coolant Level (레벨 바 + HIGH/MID/LOW 텍스트), pH, 전도도 (µS/cm) | `sensor:water_level`, `sensor:ph`, `sensor:conductivity` |
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
| Ambient Temp / Humidity | 장치 내부 온·습도 (°C / % RH) — RPi I2C/GPIO 직접 수집 (Modbus 미경유) | `sensor:ambient_temp`, `sensor:ambient_humidity` |
| Pressure | 유압 (bar, 부착 여부 미확정) | `sensor:pressure` |

**페이지 전환**: Top bar 탭 (`Monitoring` / `History`) 선택

---

### 1-2. History Page

**레이아웃 구조**

| 영역 | 위치 | 내용 |
|---|---|---|
| Top bar | 상단 | Monitoring 페이지와 동일 |
| Sidebar | 좌측 고정 폭 (좁은 고정 컬럼) | Time Range 드롭다운 + 그룹 토글 버튼 목록 |
| View area | 우측 메인 | 활성화된 그룹별 패널이 수직으로 쌓임 |

> **Sidebar 드롭다운 동작**: 클릭 시 사이드바 위에 overlay(popup)로 표시. PySide6 `QComboBox` 기본 popup 방식.

---

**History 공통 규약**

| 항목 | 규칙 |
|---|---|
| **시리즈 팔레트 (상태색과 분리)** | 파랑 `#1f77b4` · 보라 `#9467bd` · 갈색 `#8c564b` · 시안 `#17becf` · 올리브 `#bcbd22` · 핑크 `#e377c2` — Warning `#e67e22` / Critical `#e74c3c` / Normal `#27ae60`과 의미 분리 |
| **루프 구분** | L1 계열 = 파랑 `#1f77b4` / L2 계열 = 보라 `#9467bd`. Inlet·Pump·Flow = 실선 / Outlet·Fan = 점선 |
| **차트 X축 포맷** | `HH:MM:SS` — Time Range 무관 공통 |
| **Table Timestamp 포맷** | `YYYY-MM-DD HH:MM:SS` |
| **값 표기** | 소수 1자리 (예: `34.7 °C`, `12.3 L/min`, `85.0 %`) |
| **Table 정렬** | 최신이 위 (descending by timestamp) |
| **Time Range 기본값** | `5m` |
| **페이지 초기 상태** | 그룹 미활성 — View area에 placeholder `Select metrics to display` 표시 |
| **패널 동시 활성** | 제약 없음, 버튼 순서대로 수직 쌓임. 패널 높이 View area의 1/2 고정 → 3개부터 View area 수직 스크롤 |
| **활성/비활성 버튼 표현** | 활성 = 배경 `#e8f0fe` + 하단 2px 보더 `#1f77b4` / 비활성 = 투명 배경 + 하단 2px 보더 투명 (Bold 금지 — 원칙 §4) |
| **Y축 자동 스케일** | 표시 시리즈의 min/max 기반, 여유 ±5% 패딩. 축 눈금 ~7개. 눈금 레이블은 min·max를 반드시 포함 — 초기 구현 후 체감 보고 조정 |
| **No data** | 쿼리 결과가 비었거나 센서 미부착 시 구분 없이 패널 중앙에 `No data` 라벨 (20px, `#000000`) |
| **쿼리 실패** | 패널 중앙에 `Query failed` + 에러 메시지 (`#e74c3c`) |

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

**Sidebar — 그룹 토글 버튼**

```
┌──────────────────┐
│ Time Range [5m▼] │
├──────────────────┤
│ [Coolant Temp  ] │  ← 토글 버튼 (활성=강조, 비활성=일반)
│ [Flow & Pressure]│
│ [Coolant Quality]│
│ [Coolant Level ] │
│ [Ambient       ] │
│ [PWM Duty      ] │
│ [Control History]│
│ [Alarm History ] │
└──────────────────┘
```

- 버튼 탭 → View area에 해당 그룹 패널 추가/제거 (토글)
- 여러 그룹 동시 활성 가능 — 패널은 버튼 순서대로 수직 쌓임
- 개별 시리즈 선택은 패널 내부에서 처리 (사이드바에 체크박스 없음)

---

**View area — 그룹 패널 구조**

각 활성 그룹은 독립 패널로 렌더링된다.

```
┌─────────────────────────────────────────────────────────────┐
│ {그룹명}          [Line] [Table]     ○ All  ○ L1  ○ L2      │  ← 패널 헤더
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [차트 / State Timeline / Table 영역]                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**패널 렌더링 원칙**

1. **Dual Y-Axis** — 같은 그룹 내 단위가 다른 시리즈는 좌축·우축에 단위를 분리해 단일 차트로 렌더링. "All" 라디오 선택 시에만 활성화, 개별 시리즈 선택 시 단일 축.
2. **패널 높이** — View area 높이의 1/2 고정. 패널이 3개 이상이면 View area 전체를 수직 스크롤 가능한 영역으로 처리.

**패널 헤더 구성 요소**

| 요소 | 설명 |
|---|---|
| 그룹명 (좌측 bold) | 패널 제목 |
| Graph Form 토글 (중앙) | `[Line]` `[Table]` 버튼 — 현재 그룹에만 적용. 해당 그룹 렌더링 타입에 따라 표시 여부 결정 (아래 참고) |
| 시리즈 선택 (우측) | 그룹 내 시리즈를 라디오 버튼으로 선택. 그룹에 따라 `All / L1 / L2` 또는 개별 항목 |

---

**그룹별 패널 상세 — 요약**

| 그룹 | 기본 선택 | Graph Form 토글 | 시리즈 라디오 |
|---|---|---|---|
| **Coolant Temp** | All | `[Line]` `[Table]` | `○ All  ○ L1  ○ L2` |
| **Flow & Pressure** | All | `[Line]` `[Table]` | `○ All  ○ Flow Rate  ○ Pressure` |
| **Coolant Quality** | All | `[Line]` `[Table]` | `○ All  ○ pH  ○ Conductivity` |
| **Coolant Level** | (단일) | `[Timeline]` `[Table]` | (없음) |
| **Ambient** | All | `[Line]` `[Table]` | `○ All  ○ Temp  ○ Humidity` |
| **PWM Duty** | All | `[Line]` `[Table]` | `○ All  ○ Pump  ○ Fan` |
| **Control History** | All | 없음 (Table 고정) | `○ All  ○ Pump  ○ Fan` |
| **Alarm History** | (단일) | 없음 (Table 고정) | (없음) |

---

**Multi-series 색상·범례**

> 팔레트 원칙은 위 "History 공통 규약" 참고. 상태색(Warning/Critical/Normal)과 겹치지 않는 별도 팔레트 사용.

| 규칙 | 값 |
|---|---|
| L1 계열 색상 | `#1f77b4` (파랑) |
| L2 계열 색상 | `#9467bd` (보라) |
| 같은 루프 내 항목 구분 | Inlet / Pump / Flow = 실선, Outlet / Fan = 점선 |
| 독립 물리량 (Pressure) | `#8c564b` (갈색) |
| Ambient Temp | `#e377c2` (핑크) |
| Ambient Humidity | `#17becf` (시안) |

범례: 패널 차트 영역 상단에 인라인 표시 (예: `━ Inlet L1  ╌ Outlet L1  ━ Inlet L2  ╌ Outlet L2`)

---

#### Coolant Temp

**시리즈**

| 시리즈 | Prometheus 쿼리 | Redis Key | 단위 |
|---|---|---|---|
| Inlet L1 | `sensor_coolant_temp_inlet{loop="1"}` | `sensor:coolant_temp_inlet_1` | °C |
| Inlet L2 | `sensor_coolant_temp_inlet{loop="2"}` | `sensor:coolant_temp_inlet_2` | °C |
| Outlet L1 | `sensor_coolant_temp_outlet{loop="1"}` | `sensor:coolant_temp_outlet_1` | °C |
| Outlet L2 | `sensor_coolant_temp_outlet{loop="2"}` | `sensor:coolant_temp_outlet_2` | °C |

**시리즈 선택**

| 라디오 | 표시 시리즈 | Y축 |
|---|---|---|
| All | Inlet L1 · Inlet L2 · Outlet L1 · Outlet L2 (4선) | 단일 (°C) |
| L1 | Inlet L1 · Outlet L1 (2선) | 단일 (°C) |
| L2 | Inlet L2 · Outlet L2 (2선) | 단일 (°C) |

**Graph Form**

| Form | 렌더러 | 비고 |
|---|---|---|
| Line | pyqtgraph `PlotWidget` | 단일 Y축, 동일 단위 |
| Table | `QTableWidget` | All: Timestamp \| Inlet L1 \| Outlet L1 \| Inlet L2 \| Outlet L2. L1/L2: Timestamp \| Inlet \| Outlet |

**라인 스타일**

| 시리즈 | 색상 | 스타일 |
|---|---|---|
| Inlet L1 | `#1f77b4` (파랑) | 실선 |
| Outlet L1 | `#1f77b4` (파랑) | 점선 |
| Inlet L2 | `#9467bd` (보라) | 실선 |
| Outlet L2 | `#9467bd` (보라) | 점선 |

---

#### Flow & Pressure

**시리즈**

| 시리즈 | Prometheus 쿼리 | Redis Key | 단위 |
|---|---|---|---|
| Flow Rate L1 | `sensor_flow_rate{loop="1"}` | `sensor:flow_rate_1` | L/min |
| Flow Rate L2 | `sensor_flow_rate{loop="2"}` | `sensor:flow_rate_2` | L/min |
| Pressure | `sensor_pressure` | `sensor:pressure` | bar |

**시리즈 선택**

| 라디오 | 표시 시리즈 | Y축 |
|---|---|---|
| All | Flow Rate L1 · Flow Rate L2 · Pressure (3선) | 좌: L/min (Flow), 우: bar (Pressure) — Dual Y-Axis |
| Flow Rate | Flow Rate L1 · Flow Rate L2 (2선) | 단일 (L/min) |
| Pressure | Pressure (1선) | 단일 (bar) |

**Graph Form**

| Form | 렌더러 | 비고 |
|---|---|---|
| Line | pyqtgraph `PlotWidget` | "All" 선택 시 dual Y-axis (좌=L/min, 우=bar). 개별 선택 시 단일 축. |
| Table | `QTableWidget` | All: Timestamp \| Flow L1 \| Flow L2 \| Pressure. Flow Rate: Timestamp \| L1 \| L2. Pressure: Timestamp \| Value |

**라인 스타일**

| 시리즈 | 색상 | 스타일 |
|---|---|---|
| Flow Rate L1 | `#1f77b4` (파랑) | 실선 |
| Flow Rate L2 | `#9467bd` (보라) | 실선 |
| Pressure | `#8c564b` (갈색) | 실선 |

---

#### Coolant Quality

**시리즈**

| 시리즈 | Prometheus 쿼리 | Redis Key | 단위 |
|---|---|---|---|
| pH | `sensor_ph` | `sensor:ph` | — (dimensionless) |
| Conductivity | `sensor_conductivity` | `sensor:conductivity` | µS/cm |

**시리즈 선택**

| 라디오 | 표시 시리즈 | Y축 |
|---|---|---|
| All | pH · Conductivity (2선) | 좌: pH, 우: µS/cm — Dual Y-Axis |
| pH | pH (1선) | 단일 (pH) |
| Conductivity | Conductivity (1선) | 단일 (µS/cm) |

**Graph Form**

| Form | 렌더러 | 비고 |
|---|---|---|
| Line | pyqtgraph `PlotWidget` | "All" 선택 시 dual Y-axis (좌=pH, 우=µS/cm). 개별 선택 시 단일 축. |
| Table | `QTableWidget` | All: Timestamp \| pH \| Conductivity. 개별: Timestamp \| Value |

**라인 스타일**

| 시리즈 | 색상 | 스타일 |
|---|---|---|
| pH | `#17becf` (시안) | 실선 |
| Conductivity | `#bcbd22` (올리브) | 실선 |

---

#### Coolant Level

**시리즈**

| 시리즈 | Prometheus 쿼리 | Redis Key | 단위 |
|---|---|---|---|
| Coolant Level | `sensor_water_level` | `sensor:water_level` | — (discrete: 2=HIGH, 1=MIDDLE, 0=LOW) |

> 서브선택 없음 — 단일 시리즈.

**Graph Form**

| Form | 렌더러 | 비고 |
|---|---|---|
| Timeline | `StateTimelineWidget` (QPainter) | 상태 색상 블록 |
| Table | `QTableWidget` | Timestamp \| State (HIGH / MIDDLE / LOW) |

**State Timeline 위젯**

> 구현 파일: `src/local_ui/widgets/state_timeline.py` — `StateTimelineWidget(QWidget)` (신규 작성)
> pyqtgraph 미사용 — PySide6 `QPainter` 로만 구현

- X축 = 시간 (선택된 Time Range), 가로 띠 = 각 상태 구간을 색상 블록으로 표현
- 상태 색상: Normal `#27ae60` · Warning `#e67e22` · Critical `#e74c3c` · Unknown `#bdc3c7`
- X축 하단에 시간 눈금

| `sensor_water_level` 값 | 상태 레이블 | 색상 |
|---|---|---|
| 2 | HIGH | `#27ae60` |
| 1 | MIDDLE | `#e67e22` |
| 0 | LOW | `#e74c3c` |

---

#### Ambient

**시리즈**

| 시리즈 | Prometheus 쿼리 | Redis Key | 단위 |
|---|---|---|---|
| Ambient Temp | `sensor_ambient_temp` | `sensor:ambient_temp` | °C |
| Ambient Humidity | `sensor_ambient_humidity` | `sensor:ambient_humidity` | % RH |

**시리즈 선택**

| 라디오 | 표시 시리즈 | Y축 |
|---|---|---|
| All | Ambient Temp · Ambient Humidity (2선) | 좌: °C (Temp), 우: % RH (Humidity) — Dual Y-Axis |
| Temp | Ambient Temp (1선) | 단일 (°C) |
| Humidity | Ambient Humidity (1선) | 단일 (% RH) |

**Graph Form**

| Form | 렌더러 | 비고 |
|---|---|---|
| Line | pyqtgraph `PlotWidget` | "All" 선택 시 dual Y-axis (좌=°C, 우=%RH). 개별 선택 시 단일 축. |
| Table | `QTableWidget` | All: Timestamp \| Temp (°C) \| Humidity (% RH). 개별: Timestamp \| Value |

**라인 스타일**

| 시리즈 | 색상 | 스타일 |
|---|---|---|
| Ambient Temp | `#e377c2` (핑크) | 실선 |
| Ambient Humidity | `#17becf` (시안) | 실선 |

---

#### PWM Duty

**시리즈**

| 시리즈 | Prometheus 쿼리 | Redis Key | 단위 |
|---|---|---|---|
| Pump L1 | `sensor_pump_pwm_duty{loop="1"}` | `sensor:pump_pwm_duty_1` | % |
| Pump L2 | `sensor_pump_pwm_duty{loop="2"}` | `sensor:pump_pwm_duty_2` | % |
| Fan L1 | `sensor_fan_pwm_duty{loop="1"}` | `sensor:fan_pwm_duty_1` | % |
| Fan L2 | `sensor_fan_pwm_duty{loop="2"}` | `sensor:fan_pwm_duty_2` | % |

**시리즈 선택**

| 라디오 | 표시 시리즈 | Y축 |
|---|---|---|
| All | Pump L1 · Pump L2 · Fan L1 · Fan L2 (4선) | 단일 (%) |
| Pump | Pump L1 · Pump L2 (2선) | 단일 (%) |
| Fan | Fan L1 · Fan L2 (2선) | 단일 (%) |

**Graph Form**

| Form | 렌더러 | 비고 |
|---|---|---|
| Line | pyqtgraph `PlotWidget` | 단일 Y축, 0–100% |
| Table | `QTableWidget` | All: Timestamp \| Pump L1 \| Pump L2 \| Fan L1 \| Fan L2. Pump: Timestamp \| L1 \| L2. Fan: Timestamp \| L1 \| L2 |

**라인 스타일**

| 시리즈 | 색상 | 스타일 |
|---|---|---|
| Pump L1 | `#1f77b4` (파랑) | 실선 |
| Pump L2 | `#9467bd` (보라) | 실선 |
| Fan L1 | `#1f77b4` (파랑) | 점선 |
| Fan L2 | `#9467bd` (보라) | 점선 |

---

#### Control History

**시리즈**

| 시리즈 | Prometheus 쿼리 | 소스 |
|---|---|---|
| Control Cmd – Pump | `control_cmd_pump{result="success\|fail"}` | Pushgateway Push (MCG) |
| Control Cmd – Fan | `control_cmd_fan{result="success\|fail"}` | Pushgateway Push (MCG) |

**시리즈 선택**

| 라디오 | 표시 시리즈 |
|---|---|
| All | Control Cmd – Pump · Control Cmd – Fan (통합 테이블) |
| Pump | Control Cmd – Pump |
| Fan | Control Cmd – Fan |

**Graph Form**

| Form | 렌더러 | 비고 |
|---|---|---|
| Table | `QTableWidget` | Table 고정 (Line/Timeline 없음) |

**Table 컬럼**

| Timestamp | Value (%) | Result | Source |
|---|---|---|---|
| 명령 시각 | PWM duty 명령값 (0–100) | `success` / `fail` | `manual` / `auto` |

---

#### Alarm History

**시리즈**

| 시리즈 | Prometheus 쿼리 | Redis Key 패턴 | 소스 |
|---|---|---|---|
| Alarm History | `alarm_state{alarm=~".+"}` | `alarm:*` (Keyspace Events) | Exporter Pull |

> 서브선택 없음 — 선택한 Time Range 내에서 활성이었던 알람을 표시.
> 목적은 "어떤 알람이 warning/critical 상태였는가"를 확인하는 것이지 상태 전이(active↔resolved)를 나열하는 것이 아님.

**Graph Form**

| Form | 렌더러 | 비고 |
|---|---|---|
| Table | `QTableWidget` | Table 고정 (Line/Timeline 없음) |

**Table 컬럼**

| Start | End | Alarm | Level |
|---|---|---|---|
| 알람이 SET된 시각 | 알람이 DEL된 시각 — 아직 활성이면 `-` | 알람 이름 (e.g. `coolant_temp_l1_warning`) | `warning` / `critical` |

> Level 판정: alarm name suffix `_warning` → warning, `_critical` / `_detected` / `_disconnected` → critical
> 활성 구간 판정: Prometheus `alarm_state` 시계열에서 값이 1로 연속된 구간을 한 행으로 집계. 클라이언트 사이드에서 원시 샘플을 받아 구간을 재구성하는 방식을 기본으로 함 (PromQL `changes()` 의존 최소화).
> 정렬: 최신 Start가 위 (descending).

---

## 2. Web UI (Svelte)

> 당분간 설계 보류. 구현 시점에 작성 예정.

**Environment**: 노트북/모니터 브라우저 — 1280px+ 가로, 마우스+키보드
**Reference**: `assets/UI example/ui layout 1~4.png`
