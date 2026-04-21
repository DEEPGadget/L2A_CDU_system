# UI

> **Layout policy**: Local UI (PySide6) and Web UI (Svelte) use **separate layouts**.
> They share the same data sources and pages (real-time monitoring, history), but layout, information density,
> and interaction model are designed independently for each environment.
> See [UI_Design.md](UI_Design.md) for detailed layout and component specifications.

## System Access (Admin)

키오스크 모드에서 관리자가 시스템에 접근하는 방법.

| 방법 | 조건 | 명령 |
|---|---|---|
| **TTY 전환** | 물리 키보드 연결 시 | `Ctrl+Alt+F2` → tty2 터미널 로그인, `Ctrl+Alt+F1` 로 UI 복귀 |
| **SSH** | 네트워크 연결 시 | `ssh gadgetini@<IP>` — Top bar에 IP 표시됨 |

> TTY 전환 설명: PySide6 UI는 X11(`tty1`)에서 실행 중. `Ctrl+Alt+F2`로 독립된 `tty2` 터미널로 전환되며 UI는 영향받지 않음. 작업 후 `Ctrl+Alt+F1`(또는 `F7`)로 복귀.

> IP 확인: Top bar 우측에 현재 IP가 항상 표시됨 (ethernet 우선, fallback → wlan).

---

## Touch Display Hardware

| 항목 | 스펙 |
|---|---|
| 제품 | Raspberry Pi Touch Display 2 |
| 제품 링크 | https://www.adafruit.com/product/6079 |
| 크기 | 7-inch |
| 패널 치수 | 154.56 mm × 86.94 mm |
| 해상도 | 720 × 1280 px (portrait) / 1280 × 720 px (landscape) |

## Local UI (PySide6)

> Module structure and file-level descriptions: [`src/local_ui/STRUCTURE.md`](../src/local_ui/STRUCTURE.md)

**FE (PySide6)**
- 모니터링 페이지: 실시간 센서·제어·통신 상태 조회 및 표시, 펌프·팬 제어 요청
- 기록 확인 페이지: Prometheus에서 센서 이력 및 제어 명령 이력 조회 및 표시

**BE (PySide6)**
- MCG와 IPC 기반 통신 (제어 요청 전달)
- Redis Pub/Sub 구독 (`sensor:*`, `comm:*` 현재값 — MCG가 SET 시 publish, UI가 수신)
  - `comm:status` 수신 → Top bar **Link 배지** 즉시 갱신 (`ok` / `timeout` / `disconnected` — `comm:status` 값 그대로 표시)
- Redis Keyspace Notifications 구독 (`alarm:*` SET/DEL 이벤트 — 알람 발생·해제 즉시 감지)
  - 활성 알람 유무/등급 → Top bar **System 배지** 즉시 갱신 (`Normal` / `Warning` / `Critical`)
  - Link `Warning` / `Critical` 시 System 배지 `-` 표시 (데이터 없음)
- Prometheus DB 조회 (이력 데이터 소스 — 센서 이력 + 제어 명령 이력)

## WEB UI (Svelte + FastAPI)

**FE (Svelte)**
- 모니터링 페이지: 실시간 센서·제어·통신 상태 조회 및 표시, 펌프·팬 제어 요청
  - `/api/sensor/` — 센서·제어 현재값
  - `/api/sensor/comm` — 통신 상태 현재값 (별도 fetch)
  - `/api/sensor/alarms` — 활성 알람 목록
- 기록 확인 페이지: Prometheus에서 센서 이력 및 제어 명령 이력 조회 및 표시
- 접속: http://<RPi-IP>:3000 (User Laptop 등 외부 브라우저 — IP는 Local UI Top bar에서 확인)

**BE (FastAPI)**
- MCG와 REST API 기반 통신 (제어 요청 전달)
- Redis DB 조회 (현재값 전용)
  - `GET /api/sensor/` — `sensor:*` 현재값
  - `GET /api/sensor/comm` — `comm:*` 현재값
  - `GET /api/sensor/alarms` — `alarm:*` 활성 알람
- Prometheus DB 조회 (`GET /api/history/{metric}` — 이력 데이터 소스)

## Fake Data (Development / fake mode)

`config/config.yaml` 의 `mode: fake` 설정 시 활성화. MCG·PCB 없이 Redis에 가상 센서값을 주입하여 UI를 단독으로 구동할 수 있다.

**관련 파일**

| 파일 | 설명 |
|---|---|
| `src/fake_data/scenarios.py` | 시나리오 정의 — `normal` / `warning` / `critical` / `no_link`. 각 시나리오는 Redis key → `(base, min, max)` drift tuple 또는 고정 string으로 구성. 임계값 범위는 `src/thresholds.py` 상수를 참조. |
| `src/fake_data/simulator.py` | 시뮬레이터 루프 — 2초 주기로 센서값을 drift 시켜 Redis SET + Pub/Sub publish. Duty 키(`sensor:pump_pwm_duty_*`, `sensor:fan_pwm_duty_*`)는 기동 시 1회만 초기화하고 이후 덮어쓰지 않음(UI가 직접 제어). |

**서비스 구성**

| 서비스 | 역할 |
|---|---|
| `cdu-fake-simulator.service` | 시뮬레이터 프로세스 (`src/fake_data/simulator.py`) |
| `cdu-local-ui.service` | UI 프로세스 (`src/local_ui/main.py`) |

두 서비스는 **독립 프로세스**로 분리되어 있다. 시나리오 초기값(`scenarios.py`)을 변경하면 반드시 **두 서비스를 모두 재시작**해야 Redis 값이 갱신된다.

```bash
sudo systemctl restart cdu-fake-simulator.service cdu-local-ui.service
```

**초기 Duty 값**

| 키 | 초기값 | 비고 |
|---|---|---|
| `sensor:pump_pwm_duty_1` / `_2` | 60 % | NVIDIA DGX A100 최소 운용 40 % + 기동 여유 +20 % |
| `sensor:fan_pwm_duty_1` / `_2` | 15 % | 저속 기동 후 PID 수렴 대기 |

**시나리오 목록**

| 시나리오 | 내용 |
|---|---|
| `normal` | 모든 센서 정상 범위 drift |
| `warning` | 냉각수 온도 경고 구간, 수위 MIDDLE, 습도 경고 구간 |
| `critical` | 냉각수 온도 위험 구간, 누수 감지, 장치 내부 온도 위험, 통신 timeout |
| `no_link` | 센서값 유지, `comm:status = disconnected` |

---

## DB

> **Redis 설계 원칙**: Redis는 현재값 전용 DB. 이벤트 이력·명령 기록은 저장하지 않음.
> Local UI는 폴링 없이 Pub/Sub(`sensor:*`, `comm:*`) + Keyspace Notifications(`alarm:*`)로 변경 시 즉시 수신.

**Redis DB**

| Key | 설명 | 위치 | 설정 주체 |
|---|---|---|---|
| `sensor:coolant_temp_inlet_1` | 냉각수 입수 온도 (루프 1) | Inlet Manifold | Modbus Transport Manager |
| `sensor:coolant_temp_inlet_2` | 냉각수 입수 온도 (루프 2) | Inlet Manifold | Modbus Transport Manager |
| `sensor:coolant_temp_outlet_1` | 냉각수 출수 온도 (루프 1) | Outlet Manifold | Modbus Transport Manager |
| `sensor:coolant_temp_outlet_2` | 냉각수 출수 온도 (루프 2) | Outlet Manifold | Modbus Transport Manager |
| `sensor:flow_rate_1` | 유량 (루프 1) | Pump ~ Manifold 구간 (루프1) | Modbus Transport Manager |
| `sensor:flow_rate_2` | 유량 (루프 2) | Pump ~ Manifold 구간 (루프2) | Modbus Transport Manager |
| `sensor:water_level` | 수위 상태 (`2`: HIGH / `1`: MIDDLE / `0`: LOW) — MTM이 상·하위 광센서 비트 조합으로 판단해 단일 값으로 SET | Water Tank | Modbus Transport Manager |
| `sensor:ph` | pH | Water Tank | Modbus Transport Manager |
| `sensor:conductivity` | 전도도 | Water Tank | Modbus Transport Manager |
| `sensor:leak` | 누수 | 시스템 부착 (위치 미확정) | Modbus Transport Manager |
| `sensor:ambient_temp` | 장치 내부 온도 | 시스템 부착 (위치 미확정) | RPi Ambient Sensor Reader (I2C/GPIO 직접 수집 — Modbus 미경유) |
| `sensor:ambient_humidity` | 장치 내부 습도 | 시스템 부착 (위치 미확정) | RPi Ambient Sensor Reader (I2C/GPIO 직접 수집 — Modbus 미경유) |
| `sensor:pressure` | 유압 (부착 여부 미확정) | — | Modbus Transport Manager |
| `sensor:pump_pwm_duty_1` | 펌프 PWM duty (루프 1 — P1·P2 직렬, 0–100 %) | — | Modbus Transport Manager |
| `sensor:pump_pwm_duty_2` | 펌프 PWM duty (루프 2 — P3·P4 직렬, 0–100 %) | — | Modbus Transport Manager |
| `sensor:fan_pwm_duty_1` | 팬 1 PWM duty (루프 1, 0–100 %) | — | Modbus Transport Manager |
| `sensor:fan_pwm_duty_2` | 팬 2 PWM duty (루프 2, 0–100 %) | — | Modbus Transport Manager |
| `alarm:coolant_temp_l1_warning` | 수온 경고 — Loop 1 (warning) | — | Alarm / Event Manager |
| `alarm:coolant_temp_l1_critical` | 수온 위험 — Loop 1 (critical) | — | Alarm / Event Manager |
| `alarm:coolant_temp_l2_warning` | 수온 경고 — Loop 2 (warning) | — | Alarm / Event Manager |
| `alarm:coolant_temp_l2_critical` | 수온 위험 — Loop 2 (critical) | — | Alarm / Event Manager |
| `alarm:leak_detected` | 누수 감지 | — | Alarm / Event Manager |
| `alarm:water_level_warning` | 수위 부족 경고 (warning) — `sensor:water_level`=1 | — | Alarm / Event Manager |
| `alarm:water_level_critical` | 수위 위험 (critical) — `sensor:water_level`=0 | — | Alarm / Event Manager |
| `alarm:ph_warning` | pH 이상 (warning) | — | Alarm / Event Manager |
| `alarm:conductivity_warning` | 전도도 이상 (warning) | — | Alarm / Event Manager |
| `alarm:flow_rate_warning` | 유량 저하 (warning) | — | Alarm / Event Manager |
| `alarm:pressure_warning` | 유압 이상 (warning, 부착 시) | — | Alarm / Event Manager |
| `alarm:ambient_temp_warning` | 장치 내부 온도 경고 (warning) | — | Alarm / Event Manager |
| `alarm:ambient_temp_critical` | 장치 내부 온도 한계 초과 (critical) | — | Alarm / Event Manager |
| `alarm:ambient_humidity_warning` | 장치 내부 습도 경고 (warning) | — | Alarm / Event Manager |
| `alarm:ambient_humidity_critical` | 장치 내부 습도 한계 초과 (critical) | — | Alarm / Event Manager |
| `alarm:comm_timeout` | 통신 연속 실패 (warning) | — | Alarm / Event Manager |
| `alarm:comm_disconnected` | 통신 두절 (critical) | — | Alarm / Event Manager |
| `comm:status` | 현재 Modbus 통신 상태 `"ok"\|"timeout"\|"disconnected"` | Modbus Transport Manager |
| `comm:consecutive_failures` | 연속 통신 실패 횟수 (성공 시 0 리셋) | Modbus Transport Manager |
| `comm:last_error` | 마지막 오류 `{code, message, ts}` | Modbus Transport Manager |
| `control:mode` | 현재 제어 모드 `"manual"\|"auto"` (기본값: `manual`) | MCG (모드 전환 시 SET + Pub/Sub publish). Fake mode: UI 직접 write |

**Exporter**
- 독립 프로세스로 동작 (Pull 방식)
- 수집 대상: `sensor:*`, `alarm:*`
- 제외 대상: `comm:*` (통신 이력은 Pushgateway 이벤트 경로로 적재)

**Pushgateway**
- MCG가 이벤트 발생 시 직접 push (이벤트 기반 — scrape 주기와 무관하게 누락 없이 기록)
- push 메트릭:

| Metric | Label | 설명 | push 시점 |
|---|---|---|---|
| `control_cmd_pump` | `result="success\|fail"` | 명령한 pump 출력값 0~100% | 제어 명령 완료 시 |
| `control_cmd_fan` | `result="success\|fail"` | 명령한 fan 출력값 0~100% | 제어 명령 완료 시 |
| `comm_event` | `status="timeout\|disconnected\|ok"` | 통신 상태 변경 이벤트 | 상태 전환 시 |
| `comm_consecutive_failures` | — | 연속 실패 횟수 스냅샷 | 실패 발생 시 |

**Prometheus DB**
- Exporter 수집분: 센서 시계열 이력 (`sensor_*`) + 알람 상태 이력 (`alarm_state`)
- Pushgateway 수집분: 제어 명령 이력, 통신 장애 이력
- 이력 조회 쿼리 예시:
  - `sensor_coolant_temp_inlet` — 냉각수 온도 추이
  - `control_cmd_pump{result="success"}` — 성공한 펌프 제어 명령 이력
  - `control_cmd_fan{result="fail"}` — 실패한 팬 제어 명령 이력
  - `comm_event{status="timeout"}` — 통신 장애 발생 이력
