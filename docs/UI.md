# UI

## Local UI (PySide6)

**FE (PySide6)**
- 모니터링 페이지: 실시간 센서 데이터(수온·유압·유량·수위·누수·펌프·팬 상태) 조회 및 표시, 펌프·팬 제어 요청
- 기록 확인 페이지: Prometheus에서 이력 데이터 조회 및 표시

**BE (PySide6)**
- PCG와 IPC 기반 통신 (제어 요청 전달 / 결과 수신)
- Redis DB 조회 (실시간 센서 데이터 소스)
- Prometheus DB 조회 (이력 데이터 소스)

## WEB UI (Svelte + FastAPI)

**FE (Svelte)**
- 모니터링 페이지: 실시간 센서 데이터 조회 및 표시, 펌프·팬 제어 요청
- 기록 확인 페이지: 이력 데이터 조회 및 표시
- 접속: http://10.100.1.10:3000 (User Laptop 등 외부 브라우저)

**BE (FastAPI)**
- PCG와 REST API 기반 통신 (제어 요청 전달 / 결과 수신)
- Redis DB 조회 (실시간 데이터 소스)
- Prometheus DB 조회 (이력 데이터 소스)

## DB

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
| `control:pump_duty` | 펌프 duty 현재값 | Modbus Data Parser |
| `control:fan_voltage` | 팬 전압 현재값 | Modbus Data Parser |
| `alarm:coolant_temp_high` | 수온 임계치 초과 | Alarm / Event Manager |
| `alarm:leak_detected` | 누수 감지 | Alarm / Event Manager |
| `alarm:water_level_low` | 수위 부족 | Alarm / Event Manager |
| `alarm:comm_timeout` | 통신 timeout | Alarm / Event Manager |
| `control:result:pump_duty` | 마지막 pump duty 명령 결과 `{status, value, error, ts}` | Alarm / Event Manager |
| `control:result:fan_voltage` | 마지막 fan voltage 명령 결과 `{status, value, error, ts}` | Alarm / Event Manager |
| `comm:status` | 현재 Modbus 통신 상태 `"ok"\|"timeout"\|"disconnected"` | Modbus Transport Manager |
| `comm:consecutive_failures` | 연속 통신 실패 횟수 (성공 시 0 리셋) | Modbus Transport Manager |
| `comm:last_error` | 마지막 오류 `{code, message, ts}` | Modbus Transport Manager |

**Exporter**
- 독립 프로세스로 동작
- Redis의 `sensor:*`, `control:*` key를 참조하여 메트릭 수집 후 Prometheus로 전송 (Pull 방식)
- `alarm:*`, `comm:*` 키는 수집 대상 제외 (실시간 상태 플래그)

**Prometheus DB**
- Exporter로부터 수집된 시계열 메트릭 데이터 저장
- 이력 조회용 데이터 소스
