# PCB (Modbus Slave)

## 개요

- Modbus RTU Slave (MCG가 단일 Master)
- 센서 입력 수집 및 PWM / DOUT 제어 출력
- Master(MCG)와 독립적인 자율 동작 기능 내장 (Watchdog, OP_MODE, Auto Control)

---

## 운전 모드 (MB_HR_OP_MODE, HR addr=19)

| 값 | 모드 | 동작 |
|---|---|---|
| 0 | Normal (기본값) | Master 전적 제어 |
| 1 | Emergency Stop | 모든 PWM 듀티 0, 모든 DOUT Off — 즉시 적용, 램프업 무시 |
| 2 | Default Value | Flash에 저장된 `INIT_DUTY_*`, `INIT_DOUT_BITMAP` 값으로 동작 |
| 3 | Auto Control | Master 독립적으로 NTC 온도 기반 PID 제어 (제어 대상: TIM1/TIM2/TIM8 PWM) |

---

## Master Heartbeat Watchdog

| 항목 | 레지스터 | 설명 |
|---|---|---|
| `MASTER_HEARTBEAT` | HR addr=20 | MCG가 주기적으로 갱신하는 카운터 (0~65535, 롤오버 허용) |
| `WATCHDOG_TIMEOUT` | Flash | 값 변경 없이 경과 허용 시간 (기본값: 5초) |
| `WATCHDOG_ACTION_POLICY` | Flash | Timeout 시 자동 전환할 OP_MODE 선택 (0=비활성화 / 1=비상정지 / 2=기본값 / 3=자동제어) |

> MCG가 `MASTER_HEARTBEAT`를 갱신하지 않으면 `WATCHDOG_TIMEOUT` 경과 후 PCB가 `WATCHDOG_ACTION_POLICY`에 따라 자동으로 OP_MODE 전환.
> 롤오버(65535 → 0)는 정상 갱신으로 인정.

---

## Flash 저장 파라미터

| 파라미터 | 범위 | 기본값 | 설명 |
|---|---|---|---|
| `WATCHDOG_TIMEOUT` | 0~10 | 5 | Heartbeat 감시 timeout (초) |
| `WATCHDOG_ACTION_POLICY` | 0~3 | 0 | Timeout 시 OP_MODE 동작 선택 |
| `RAMP_UP_DELAY` | 0~100 | 10 | 소프트 스타트 지연 (10 = PWM 0→1000을 1초에 걸쳐 증가), 0=비활성화 |
| `INIT_DUTY_TIM1` | 0~1000 | 0 | OP_MODE=2 시 TIM1 PWM duty |
| `INIT_DUTY_TIM2` | 0~1000 | 0 | OP_MODE=2 시 TIM2 PWM duty |
| `INIT_DUTY_TIM8` | 0~1000 | 0 | OP_MODE=2 시 TIM8 PWM duty |
| `INIT_DOUT_BITMAP` | 6bit | 000000 | OP_MODE=2 시 DOUT 1~6 초기 출력 상태 |
| `DOUT_HIGH_VOL` | 0, 1 | — | DOUT High 전압 선택 (0=12V, 1=24V) |
| `AUTO_TARGET_NTC_TEMP` | 0~100 | 30 | OP_MODE=3 자동제어 목표 온도 (°C) |

> Flash 파라미터는 `HR CONFIG_CONTROL` 명령으로 설정 가능.

---

## 동작 시나리오

| 시나리오 | 관련 파라미터 | 동작 |
|---|---|---|
| MCG 다운 / 통신 두절 | `MASTER_HEARTBEAT`, `WATCHDOG_TIMEOUT`, `WATCHDOG_ACTION_POLICY` | Watchdog Timeout 후 지정된 OP_MODE로 자동 전환 |
| 즉시 출력 차단 | `MB_HR_OP_MODE=1` | 모든 PWM·DOUT 즉시 0/Off (램프업 무시) |
| 전원 재인가 | `INIT_DUTY_*`, `INIT_DOUT_BITMAP`, `RAMP_UP_DELAY` | Flash 초기값 로드 후 램프업 적용 |
| 출력 급상승(Inrush) 완화 | `RAMP_UP_DELAY`, `INIT_DUTY_TIM1/2/8` | 기동 시 PWM 듀티를 설정 시간에 따라 단계적으로 상승 — 기동 충격·전원 피크 부하 완화 |
| 현장별 DOUT 전압 규격 대응 | `DOUT_HIGH_VOL`, `INIT_DOUT_BITMAP` | 설정만으로 12V/24V 대응, 기동 시 DOUT이 사전 정의된 안전 비트맵 상태로 켜짐 |
| Master 없이 온도 제어 | `MB_HR_OP_MODE=3`, `AUTO_TARGET_NTC_TEMP` | NTC 온도 기반 PID로 PWM 자동 제어 |

---

## 안전 처리 규칙

| 항목 | 조건 | 처리 |
|---|---|---|
| 비상정지 우선순위 | `OP_MODE=1` 수신 | 램프업·완만 정지 무시, 즉시 0/Off |
| 값 범위 외 입력 | 정의 범위 벗어난 레지스터 값 | 쓰기 무시, 최근 유효값 또는 클램핑 유지 |
| Flash 무결성 실패 | 전원 인가 시 CRC 오류 | 손상 파라미터만 공장 기본값 복원, 오류 플래그 설정 |
| Watchdog 복귀 | Heartbeat 복구 후 | 보호 모드 유지 — 수동 복귀 명령(`OP_MODE=0`) 수신 전까지 유지 |
| 자동제어 센서 이상 | `OP_MODE=3`에서 NTC 이상 | 자동제어 중단, 안전 모드 전환 또는 PWM 안전 수준 제한 |

---

## TODO (추가 협의 필요)

| 항목 | 확인 필요 내용 |
|---|---|
| 설정값 리셋 범위 | `MB_RESET_CMD=1` 시 Flash 저장값까지 공장초기화 포함 여부 (전부 / 일부 / 미포함) |
| Watchdog 복귀 정책 | Heartbeat 복구 후 자동복귀 vs 수동복귀 (레지스터/코일 트리거) 결정 |
| INIT_DOUT_BITMAP 적용 방식 | 전원 인가 시 즉시 반영 시점 및 안전지연 유무 |
