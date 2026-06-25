# [RESEARCH] L2A CDU 터치모니터 개발

## 개요

본 문서는 L2A CDU 시스템의 전체 아키텍처와 요구사항, 그리고 HW/SW 구성 요소를 정의함. 본 문서는 시스템의 큰 구조와 설계 기준을 설명하는 것을 목적으로 하며, 세부 구현 사항은 추후 지속적으로 업데이트한다.

**Last Update:** 2026.06.25

## Table of Contents

1. L2A CDU 시스템 전체 구성
2. 요구사항
3. 통신
   - 3.1 통신 구조
   - 3.2 통신 방식
   - 3.3 Modbus 동작
4. 시스템 구성 요소 상세
   - 4.1 Raspberry Pi (Modbus Master)
   - 4.2 Modbus Control Gateway (MCG)
   - 4.3 UI
   - 4.4 PCB (Modbus Slave)
   - 4.5 Sensor / Actuator
5. 사용자 인터페이스 설계
   - 5.1 UI 선정 기준
   - 5.2 UI 후보 비교
6. 라즈베리파이 키오스크 모드 설계
7. Versioning (LTS policy)
8. TODO

---

## 1. L2A CDU 시스템 전체 구성

![L2A CDU 시스템 전체 구성](assets/l2a_cdu_system_architecture.png)

| 구성 요소 | 역할 |
|---|---|
| Raspberry Pi | MCG, UI, DB를 탑재하는 하드웨어 플랫폼 (IP: DHCP 할당 — Local UI Top bar에서 확인). 온/습도 센서를 I2C/GPIO로 직접 연결하여 읽음 (예외적 직접 수집 — Modbus 미경유) |
| Web UI (Svelte + FastAPI) | WEB 기반 유저 인터페이스. SvelteKit 정적 프리렌더(adapter-static) 빌드를 FastAPI(:8000)가 서빙, nginx :80 → :8000 프록시. FastAPI는 Redis 매개로 MCG와 통신. 모니터링 및 제어 화면, 과거 기록 확인 화면 |
| Touch Display UI (PySide6) | 로컬 기반 유저 인터페이스. Redis (Pub/Sub + Hash) 매개로 MCG 와 통신. 모니터링 및 제어, 과거 기록 확인 화면 |
| Redis DB | 실시간 상태 + 설정 저장 (`sensor:*`, `comm:*`, `control:mode`, `control:fan_curve`, `control:pump_duty_1`/`_2` 루프별 독립) + UI ↔ MCG Pub/Sub 매개체. **Persistence (RDB + AOF, fsync everysec) 활성** — `control:*` 설정값은 재시작/전원 인가 후 자동 복원. 시계열 이력은 Prometheus 담당 |
| Prometheus + Exporter | 과거 이력 DB. Exporter가 Redis `sensor:*` + `alarm:*` 를 주기적으로 pull → 시계열 적재 |
| Prometheus Pushgateway | 이벤트성 이력 수신 (제어 명령·통신 장애). MCG가 이벤트 발생 시 직접 push |
| Modbus Control Gateway (MCG) | 실질적 Modbus Master (읽기/쓰기). 읽기: pcb 로부터 polling → redis에 전송. 쓰기: UI 로부터 요청받음 → PCB 로 write 명령 |
| PCB | Modbus Slave, 센서 입력 및 펌프/팬 제어 |
| 센서 및 엑츄에이터 | 센서: 수온, 유량, 유압, 누수, 수위센서. 엑츄에이터: 펌프, 팬 |

> **DB 설계 원칙**
> - **Redis** — 실시간 상태 + 설정 저장. RDB + AOF persistence 활성 (`appendonly yes`, `appendfsync everysec`) 으로 `control:*` 설정값은 영구 보존되며 재시작 후 자동 복원. `sensor:*` / `comm:*` / `alarm:*` 도 같은 DB 에 있으나 매 cycle 갱신되므로 영구 보존 불요. 시계열 이력은 Prometheus 담당.
> - **Race condition 정책** — Last-write-wins + Pub/Sub 즉시 반영. Local UI 와 Web UI (FastAPI 백엔드) 둘 다 같은 Redis 키를 SET 하며, 늦은 쪽이 이김. Pub/Sub 으로 다른 UI 는 즉시 변경된 값을 받아 표시.
> - **Prometheus** — 과거 이력을 보기 위한 저장소. 두 가지 적재 경로:
>   - **Exporter (Pull)**: Redis에 쌓인 연속형 상태값(`sensor:*`, `alarm:*`)을 주기적으로 pull → 시계열 적재
>   - **Pushgateway (Push)**: 이벤트성 이력(제어 명령 결과, 통신 상태 변경 등)을 발생 시점에 MCG가 직접 push


## 2. 요구사항

- 사용자는 터치 디스플레이 또는 웹 UI를 통해 시스템을 모니터링하고 제어할 수 있어야 함
- 시스템은 수동(Manual) 및 자동(Auto) 두 가지 제어 모드를 지원하며, 사용자는 UI를 통해 모드를 전환할 수 있어야 함
- 시스템은 키오스크 사용자에게 제한된 기능만 노출해야 함
- 시스템은 사용자에게 하드웨어 플랫폼 정보 (라즈베리파이 기반 여부, OS 정보 등)를 노출하지 않아야 함
- 시스템은 부팅 완료 후 사용자 개입 없이 제어 서비스 및 사용자 인터페이스를 자동으로 실행해야 함


## 3. 통신

### 3.1 통신 구조

- MCG는 Modbus 통신의 단일 Master로 동작
- 모든 센서 데이터 조회 및 제어 요청은 MCG를 통해 처리됨
- UI는 MCG와만 통신하며 PCB와 직접 통신하지 않음

> **예외 — 온/습도 센서**: 장치 내부 온도·습도 센서(`sensor:ambient_temp`, `sensor:ambient_humidity`)는 PCB를 경유하지 않고 Raspberry Pi에 직접 연결(I2C/GPIO)하여 수집함. 별도의 RPi Ambient Sensor Reader 프로세스가 값을 읽어 Redis에 직접 SET.

### 3.2 통신 방식

| 구간 | 방식 |
|---|---|
| MCG ↔ PCB | Modbus RTU (Master / Slave) |
| Touch Display UI ↔ MCG | **Redis** (Pub/Sub + Hash) — UI 는 `control:mode` / `control:fan_curve` / `control:pump_duty` / duty 키를 SET, MCG 는 매 cycle Pub/Sub drain 으로 픽업 |
| Web UI (Svelte) ↔ FastAPI 백엔드 | REST API (write: PUT `/api/control/*`) + **WebSocket `/ws`** (sync: 백엔드가 Redis Pub/Sub 구독 → 모든 클라이언트에 push) |
| FastAPI 백엔드 ↔ Redis | Pub/Sub 구독 + Hash/String R/W |
| RPi ↔ 온/습도 센서 | I2C / GPIO (직접 연결 — Modbus 미경유) |

### 3.3 Modbus 동작

- **Read**: MCG가 PCB에 주기적으로 polling → 센서·상태 레지스터 읽기
- **Write**: UI 제어 요청 수신 시 MCG가 PCB에 write 명령 전송


## 4. 시스템 구성 요소 상세

### 4.1 Raspberry Pi (Modbus Master)

- MCG, UI, DB를 탑재하는 하드웨어 플랫폼
- 구성요소
  - UI: 4.3 참고
  - MCG: 4.2 참고
  - DB: Redis DB, Prometheus (상세 내용은 4.3 DB 참고)
- **온/습도 센서 직접 수집 (예외)**
  - 장치 내부 온도·습도 센서를 I2C/GPIO로 직접 연결
  - RPi Ambient Sensor Reader 프로세스가 주기적으로 값을 읽어 Redis에 SET (`sensor:ambient_temp`, `sensor:ambient_humidity`)
  - MCG Modbus polling 대상에서 제외

### 4.2 Modbus Control Gateway (MCG)

- 시스템 내 중앙 제어 및 통신 허브 (Modbus Master)
- **단일 쓰레드 메인 루프** + Redis Pub/Sub 비차단 drain. Modbus 가 단일 시리얼 버스(순차 제약)라 쓰레드 분리 이득이 작음. 참고 구현: `gadgetini/src/control_board/main_loop.py` (동일 사상, 매개체만 `config.yaml` mtime polling).
- UI 명령은 Redis 키에 SET (예: `sensor:pump_pwm_duty_x`, `control:mode`, `control:auto`) → 메인 루프가 다음 cycle 에서 변경분 픽업 후 Modbus Write. 별도 큐/IPC 소켓 없음.
- **제어 모드 (Manual / Auto)**:
  - **Manual**: 사람이 UI에서 Pump/Fan PWM을 직접 설정. 시스템은 감지·알람만 담당.
  - **Auto**: MCG가 냉각수온·유량 기반으로 지정된 알고리즘에 의해 Pump/Fan PWM을 자동 계산 → Modbus write. 사람은 모드 전환·모니터링 담당. (**기동 default 는 Manual + Pump UI 78 % / Fan 100 %** — MCG.md §7)
  - 모드 전환은 UI 요청으로만 발생
  - 현재 모드는 Redis `control:mode` 키로 관리 (`manual` / `auto` / `emergency`). 쓰기 주체는 UI 서비스 (최초 기동 시 `auto`로 SETNX, 이후 토글 시 직접 SET). MCG는 읽기만 함.
  - MCG가 제어 주체. PCB는 단순 R/W Slave (OP_MODE/Watchdog 미구현 — 향후 펌웨어 업데이트 필요)
  - Auto 모드에서 Pump/Fan 수동 제어 UI는 비활성화 (Manual 전환 시 재활성화)
  - Emergency 모드: TODO — 시스템 안정화 후 설계

> 상세 내용: [MCG.md](docs/MCG.md)

### 4.3 UI

- Local UI (PySide6): 터치 디스플레이 기반, Redis (Pub/Sub + Hash)로 MCG와 통신
- WEB UI (Svelte + FastAPI): 브라우저 기반, REST API로 MCG와 통신
- 양쪽 모두 모니터링 페이지 / 기록 확인 페이지로 구성
- DB: Redis (실시간), Prometheus (이력)

> 상세 내용: [UI.md](docs/UI.md)

### 4.4 PCB (Modbus Slave) — MCS_IO Board REV_C

- STM32G474 기반 다목적 I/O 제어 보드
- 센서 입력 값 제공 (ADC 8ch 전압 + 4ch NTC 온도, Pulse 12ch, DIN 6ch)
- 펌프 및 팬 제어 출력 수행 (PWM 12ch, DOUT 6ch)
- Modbus RTU Slave — MCG 명령에 따른 레지스터 Read / Write 수행
- PWM 변경 시 S-Curve 1초 고정 램프 적용
- Flash 저장: PWM 주파수, 극성, ADC 게인 (PWM Duty/DOUT 초기값은 미저장 — MCG 서비스 초기화로 대체)
- **미구현 (향후 펌웨어 업데이트 필요)**: Watchdog (Master Heartbeat 감시), OP_MODE (운전 모드 전환)
- 상세 내용: [PCB.md](docs/PCB.md)

### 4.5 Sensor / Actuator

- 수위, 유량, 수온 등 시스템 동작에 필요한 센서 데이터 제공
- 펌프, 팬 등 제어 대상 액추에이터 포함
- PCB를 통해 MCG에 의해 간접적으로 제어됨

> **예외 — 온/습도 센서**: 장치 내부 온도·습도 센서는 PCB에 연결되지 않고 Raspberry Pi에 직접 연결(I2C/GPIO)됨. 데이터 경로: 센서 → RPi Ambient Sensor Reader → Redis (`sensor:ambient_temp`, `sensor:ambient_humidity`)


## 5. 사용자 인터페이스 설계 (참고)

### 5.1 UI 선정 기준

- 키오스크 모드 동작 가능
- 제어 요청에 대한 저지연 응답
- 상업적 사용 가능 라이선스
- 커스텀 UI 구성 용이성

### 5.2 UI 후보 비교 (참고)

| 항목 | FlowFuse Dashboard | Grafana | PyQt6 | PySide6 |
|---|---|---|---|---|
| 상업 판매 비용 | 무료 | 무료 | $550/년 | 무료 |
| 웹 기반 | O | O | X | X |
| 데이터 수신 지연 | 5~20ms | 100~1000ms | <1ms | <1ms |
| 제어 요청 지연 | 20~60ms | 50~200ms | <1ms | <1ms |
| 키오스크 지원 | O | O | O | O |
| 커스텀 자유도 | 중간 | 높음 | 매우 높음 | 매우 높음 |
| 메모리 사용량 | 200~300MB | 200~300MB | 50~100MB | 50~100MB |


## 6. 라즈베리파이 키오스크 모드 설계

> 상세 내용: [Kiosk.md](docs/Kiosk.md)


**Local UI (PySide6) 키오스크**
- 부팅 후 자동 로그인
- PySide6 앱 자동 실행 (브라우저 불필요)
- 전체화면 모드 강제 적용
- 앱 비정상 종료 시 자동 재시작
- 화면 절전 및 전원 관리 비활성화
- 마우스 커서 숨김

> WEB UI는 원격 브라우저 접속용 (http://\<RPi-IP\> — nginx :80 → FastAPI :8000) — 키오스크 모드 해당 없음


## 7. Versioning (LTS policy)

L2A CDU 는 현재 **MCS_IO Board REV_C** 에 묶여있고, 향후 **REV_D** + 호환 센서 확정 시점에 신 기능(예: pH / Conductivity)이 추가될 예정이다. 운용 안정성 보장을 위해 **REV_C 기준 코드 베이스를 LTS v1 태그로 고정**한다.

### LTS v1 — current baseline

| 영역 | 현재 (LTS v1) | 미래 PCB 업그레이드 시 |
|---|---|---|
| **pH 측정** | 미지원 — `sensor:ph` redis 키 미emit, UI placeholder `-`, alarm 미발생 | PCB chemistry analog 입력 + 호환 pH 센서 확정 시 재도입 |
| **Conductivity 측정** | 미지원 — 동일 (`sensor:conductivity` 미emit) | 동일 |
| **Flow 측정** | Rev_C+ 실 유량 센서 (루프당 2개 = 총 4개, SIKA VVX15 PushPull 주파수 500 pulse/L → IR 13~16, 루프별 2개 합산, Q=0.12×Hz). 센서 전원은 CH1~4 'V' 핀(12V, duty 100%). 유량은 **실측값**이며 펌프 duty 추정이 아님. **Modbus 링크가 살아있으면 항상 측정**(별도 enable 플래그 없음), 센서/링크 미가용 시 `sensor:flow_rate_*` 미발행 → UI no-data. [PCB.md "유량"](docs/PCB.md) 참고 | (없음 — 링크 기반 자동) |
| **Pressure 측정** | 시스템 자체에서 제외 (현재 UI / 알람 / Prometheus 모두 미사용) | 추후 결정 |
| **Watchdog (PCB heartbeat 감시)** | PCB 펌웨어 미구현 — MCG 소프트웨어 측 모니터링으로 대체 | PCB 펌웨어 업데이트 시 [PCB.md "미구현 기능"](docs/PCB.md) 참고 |
| **OP_MODE / Flash 초기값 / DOUT 12-24V** | 미지원 (PCB 펌웨어) | 동일 |

### 운용 원칙

1. **LTS v1 코드 베이스에는 미측정 항목용 placeholder 자체를 유지하지 않는다** — redis 키 미emit, UI 측은 default `-`, threshold/alarm 코드는 제거. 이로써 "측정 안 함" 이 시스템 전반에서 일관 표현됨.
2. **각 미지원 항목은 docs 안에 LTS v1 표시**가 유지된다 ([threshold.md "Chemistry"](docs/threshold.md), [MCG.md §9](docs/MCG.md), [UI_Design.md "Coolant Quality"](docs/UI_Design.md), [auto_control.md §1](docs/auto_control.md)). 미래에 재도입할 때 변경 범위 추적이 용이하다.
3. **재도입 절차** (미래 PCB 업그레이드 시):
   - `src/thresholds.py` 의 `PH_*` / `CONDUCTIVITY_*` 상수 복원
   - `src/local_ui/widgets/cooling_health.py` 의 `_KEY_TO_PLACEHOLDER` 매핑 + color 함수 복원
   - `src/local_ui/widgets/alarm_overlay.py` 의 알람 라벨 복원
   - 위 docs 의 "LTS v1: not emitted / deprecated" 노트 제거 후 표 활성화
4. **git tag**: LTS v1 시점에 `v1.0-lts` 태그 마킹 (PCB 업그레이드 후 v2 분기 기점).
