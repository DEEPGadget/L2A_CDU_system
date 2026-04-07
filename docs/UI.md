# UI

> **Layout policy**: Local UI (PySide6) and Web UI (Svelte) use **separate layouts**.
> They share the same data sources and pages (real-time monitoring, history), but layout, information density,
> and interaction model are designed independently for each environment.
> See [UI_Design.md](UI_Design.md) for detailed wireframes.

## Touch Display Hardware

| 항목 | 스펙 |
|---|---|
| 제품 | Raspberry Pi Touch Display 2 |
| 제품 링크 | https://www.adafruit.com/product/6079 |
| 크기 | 7-inch |
| 패널 치수 | 154.56 mm × 86.94 mm |
| 해상도 | 720 × 1280 px (portrait) / 1280 × 720 px (landscape) |

## Local UI (PySide6)

**FE (PySide6)**
- 모니터링 페이지: 실시간 센서·제어·통신 상태 조회 및 표시, 펌프·팬 제어 요청
- 기록 확인 페이지: Prometheus에서 센서 이력 및 제어 명령 이력 조회 및 표시

**BE (PySide6)**
- PCG와 IPC 기반 통신 (제어 요청 전달)
- Redis Pub/Sub 구독 (`sensor:*`, `comm:*` 현재값 — PCG가 SET 시 publish, UI가 수신)
- Redis Keyspace Notifications 구독 (`alarm:*` SET/DEL 이벤트 — 알람 발생·해제 즉시 감지)
- Prometheus DB 조회 (이력 데이터 소스 — 센서 이력 + 제어 명령 이력)

## WEB UI (Svelte + FastAPI)

**FE (Svelte)**
- 모니터링 페이지: 실시간 센서·제어·통신 상태 조회 및 표시, 펌프·팬 제어 요청
  - `/api/sensor/` — 센서·제어 현재값
  - `/api/sensor/comm` — 통신 상태 현재값 (별도 fetch)
  - `/api/sensor/alarms` — 활성 알람 목록
- 기록 확인 페이지: Prometheus에서 센서 이력 및 제어 명령 이력 조회 및 표시
- 접속: http://10.100.1.10:3000 (User Laptop 등 외부 브라우저)

**BE (FastAPI)**
- PCG와 REST API 기반 통신 (제어 요청 전달)
- Redis DB 조회 (현재값 전용)
  - `GET /api/sensor/` — `sensor:*` 현재값
  - `GET /api/sensor/comm` — `comm:*` 현재값
  - `GET /api/sensor/alarms` — `alarm:*` 활성 알람
- Prometheus DB 조회 (`GET /api/history/{metric}` — 이력 데이터 소스)

## DB

> **Redis 설계 원칙**: Redis는 현재값 전용 DB. 이벤트 이력·명령 기록은 저장하지 않음.
> Local UI는 폴링 없이 Pub/Sub(`sensor:*`, `comm:*`) + Keyspace Notifications(`alarm:*`)로 변경 시 즉시 수신.

**Redis DB**

| Key | 설명 | 설정 주체 |
|---|---|---|
| `sensor:coolant_temp_inlet` | 냉각수 입수 온도 | Modbus Data Parser |
| `sensor:coolant_temp_outlet` | 냉각수 출수 온도 | Modbus Data Parser |
| `sensor:ambient_temp` | 외기 온도 | Modbus Data Parser |
| `sensor:ambient_humidity` | 외기 습도 | Modbus Data Parser |
| `sensor:pressure` | 유압 | Modbus Data Parser |
| `sensor:flow_rate` | 유량 | Modbus Data Parser |
| `sensor:water_level` | 수위 | Modbus Data Parser |
| `sensor:leak` | 누수 | Modbus Data Parser |
| `sensor:pump_status` | 펌프 상태 | Modbus Data Parser |
| `sensor:fan_status` | 팬 상태 | Modbus Data Parser |
| `alarm:coolant_temp_warning` | 수온 경고 (warning) | Alarm / Event Manager |
| `alarm:coolant_temp_critical` | 수온 위험 (critical) | Alarm / Event Manager |
| `alarm:leak_detected` | 누수 감지 | Alarm / Event Manager |
| `alarm:water_level_warning` | 수위 부족 경고 (warning) | Alarm / Event Manager |
| `alarm:water_level_critical` | 수위 위험 (critical) | Alarm / Event Manager |
| `alarm:pressure_warning` | 유압 이상 (warning) | Alarm / Event Manager |
| `alarm:flow_rate_warning` | 유량 저하 (warning) | Alarm / Event Manager |
| `alarm:ambient_temp_warning` | 주변 온도 경고 (warning) | Alarm / Event Manager |
| `alarm:ambient_temp_critical` | 주변 온도 한계 초과 (critical) | Alarm / Event Manager |
| `alarm:ambient_humidity_warning` | 주변 습도 경고 (warning) | Alarm / Event Manager |
| `alarm:ambient_humidity_critical` | 주변 습도 한계 초과 (critical) | Alarm / Event Manager |
| `alarm:comm_timeout` | 통신 연속 실패 (warning) | Alarm / Event Manager |
| `alarm:comm_disconnected` | 통신 두절 (critical) | Alarm / Event Manager |
| `comm:status` | 현재 Modbus 통신 상태 `"ok"\|"timeout"\|"disconnected"` | Modbus Transport Manager |
| `comm:consecutive_failures` | 연속 통신 실패 횟수 (성공 시 0 리셋) | Modbus Transport Manager |
| `comm:last_error` | 마지막 오류 `{code, message, ts}` | Modbus Transport Manager |

**Exporter**
- 독립 프로세스로 동작 (Pull 방식)
- 수집 대상: `sensor:*`
- 제외 대상: `alarm:*`, `comm:*` (실시간 상태 플래그, 이력 불필요)

**Pushgateway**
- PCG가 이벤트 발생 시 직접 push (이벤트 기반 — scrape 주기와 무관하게 누락 없이 기록)
- push 메트릭:

| Metric | Label | 설명 | push 시점 |
|---|---|---|---|
| `control_cmd_pump` | `result="success\|fail"` | 명령한 pump 출력값 0~100% | 제어 명령 완료 시 |
| `control_cmd_fan` | `result="success\|fail"` | 명령한 fan 출력값 0~100% | 제어 명령 완료 시 |
| `comm_event` | `status="timeout\|disconnected\|ok"` | 통신 상태 변경 이벤트 | 상태 전환 시 |
| `comm_consecutive_failures` | — | 연속 실패 횟수 스냅샷 | 실패 발생 시 |

**Prometheus DB**
- Exporter 수집분: 센서·제어 현재값의 시계열 이력
- Pushgateway 수집분: 제어 명령 이력, 통신 장애 이력
- 이력 조회 쿼리 예시:
  - `sensor_coolant_temp_inlet` — 냉각수 온도 추이
  - `control_cmd_pump{result="success"}` — 성공한 펌프 제어 명령 이력
  - `control_cmd_fan{result="fail"}` — 실패한 팬 제어 명령 이력
  - `comm_event{status="timeout"}` — 통신 장애 발생 이력
