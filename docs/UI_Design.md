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
| 8 | **컴포넌트 이름 헤더 규칙** — 레인 내 컴포넌트(Pump·Flow·Inlet Manifold·Outlet Manifold·Fan+Radiator)는 상단 공통 헤더에 이름 표시, 박스 내부는 값만 렌더링. 레인 좌측에 "Loop 1" / "Loop 2" 행 레이블로 구분. Reservoir는 좌단 공유 컴포넌트로 박스 내부에 이름 표시. Server 1·2는 레인 외부(위·아래)에 위치하므로 박스 내부에 이름 표시. |
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
| `coolant_temp_inlet` | Prometheus |
| `coolant_temp_outlet` | Prometheus |
| `pressure` | Prometheus |
| `flow_rate` | Prometheus |
| `pump_pwm_duty` | Prometheus |
| `fan_pwm_duty` | Prometheus |
| `control_cmd` (pump / fan) | Prometheus |
| `comm_event` | Prometheus |

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
