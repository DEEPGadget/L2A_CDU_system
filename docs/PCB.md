# PCB (Modbus Slave) — MCS_IO Board Rev2

## 개요

- STM32G474 기반 다목적 I/O 제어 보드
- Modbus RTU Slave (RS485 절연) + USB CDC (CLI + Modbus RTU 겸용)
- MCG가 단일 Master — PCB는 레지스터 읽기/쓰기 명령을 수행하는 역할만 담당

---

## 주요 사양

| 항목 | 사양 |
|---|---|
| PWM 출력 | 12ch (Duty 0~1000 = 0.0~100.0%, S-Curve 1초 고정) |
| ADC 입력 | 8ch 전압 (0~12V) + 4ch NTC 온도 |
| 펄스 입력 | 12ch 주파수 (0~10KHz, Falling Edge) |
| 디지털 I/O | 입력 6ch / 출력 6ch |
| 통신 | RS485 Modbus RTU (절연, 8N1) + USB CDC |
| Flash 저장 | PWM 주파수, 극성, ADC 게인 |

---

## 하드웨어 설정

### DIP 스위치

| 스위치 | 기능 | 설명 |
|---|---|---|
| DIP 1~5 | Modbus Slave ID | 2진수 (1~31), 모두 OFF이면 ID=1 |
| DIP 6 | Baud Rate | OFF: 9600 / ON: 115200 |

### LED

| LED | 명칭 | 동작 |
|---|---|---|
| LED 1 | System Heartbeat | 0.25초 점멸 (시스템 정상) |
| LED 2 | Modbus Activity | RS485 송수신 시 점등 |
| LED 3 | USB Activity | USB 송수신 시 점등 |

### 버튼

| 버튼 | 기능 | 동작 |
|---|---|---|
| BT1 | OLED Mode | 디스플레이 페이지 전환 (메인/ADC 뷰) |
| BT2 | Factory Reset | 3초 롱프레스: PWM Duty→0, Freq→1kHz, Pol→기본, DOUT→OFF 초기화 후 Flash 저장 (ADC 게인 유지) |
| BT3 | ADC Calibration | 3초 롱프레스: ADC 캘리브레이션 (BT3 누른 채 부팅 시 캘리브레이션 모드 진입) |

---

## Modbus 레지스터 맵

### Holding Registers (FC 03/06/10) — R/W

| 주소 | 기능 | 설명 | 범위 |
|---|---|---|---|
| 0~11 | PWM Duty | CH1~12 듀티비 | 0~1000 (0.0~100.0%) |
| 12 | PWM Freq (TIM1) | CH1~4 주파수 | 1000~25000 Hz |
| 13 | PWM Freq (TIM2) | CH5~8 주파수 | 1000~25000 Hz |
| 14 | PWM Freq (TIM8) | CH9~12 주파수 | 1000~25000 Hz |
| 15 | Digital Output | DOUT1~6 비트패킹 | bit0=DOUT1 ~ bit5=DOUT6 |
| 16 | PWM Polarity | 극성 설정 (1=반전) | bit0~11 (CH1~12) |
| 17 | Config Command | 설정 저장/로드 | 0x01=Save, 0x02=Load |
| 18 | Config Status | 저장/로드 결과 | 상태 비트마스크 |
| 19~26 | ADC Gain | CH1~8 게인 보정값 | 1000=1.000x (기본값) |

### Input Registers (FC 04) — R/O

| 주소 | 기능 | 설명 | 단위/형식 |
|---|---|---|---|
| 0 | System Timer | 시스템 가동 시간 | 0~9999 초 |
| 1~12 | ADC Raw Data | ADC 12채널 원시값 | 0~4095 (12-bit) |
| 13~24 | Pulse Freq | 펄스 주파수 12채널 | 0~65535 Hz |
| 25 | DIN Status | 디지털 입력 DIN1~6 | bit0~5 |
| 26 | Pulse State | 펄스 핀 H/L 상태 | bit0~11 |
| 27 | DIP Switch | DIP 스위치 1~6 | bit0~5 |
| 28~31 | NTC Temp | NTC 온도 (CH13~16) | 0.1°C (253=25.3°C) |
| 32~39 | Voltage | 전압 (CH1~8) | 0.01V (900=9.00V) |

### Coils (FC 01/05/0F) — R/W

| 주소 | 기능 | 설명 |
|---|---|---|
| 0~5 | Digital Output | DOUT1~DOUT6 개별 ON/OFF |

### Discrete Inputs (FC 02) — R/O

| 주소 | 기능 | 설명 |
|---|---|---|
| 0~5 | Digital Input | DIN1~DIN6 상태 |
| 6~8 | Buttons | BT1~BT3 버튼 상태 |

---

## PWM S-Curve 램프

PWM 듀티 변경 시 목표값까지 **1초**에 걸쳐 S-Curve (smoothstep) 보간으로 부드럽게 전환.

- 보간 공식: s(t) = 3t² - 2t³ (t = 경과시간 / 1초)
- 10ms 주기 업데이트 → 100단계
- 시작과 끝에서 기울기 = 0 (가속 → 등속 → 감속)
- 램핑 중 새 목표값 설정 시 현재값에서 새 목표로 재시작
- S-Curve 시간은 **1초 고정** (가변 설정 불가)

---

## Flash 저장 항목

Config Command(HR 17)에 0x01을 쓰거나, BT2 Factory Reset 시 자동 저장.

| 항목 | 설명 | 기본값 |
|---|---|---|
| pwm_freq[3] | TIM1/TIM2/TIM8 주파수 | 1000 Hz |
| pwm_polarity | PWM 극성 12비트 마스크 | 0x0000 (Active High) |
| adc_gain[8] | ADC 캘리브레이션 게인 (CH1~8) | 1000 (1.0x) |

> PWM Duty, DOUT 상태의 Flash 저장은 미지원 — 전원 재인가 시 MCG가 초기값을 write하여 보정 (MCG.md "서비스 초기화" 참고).

---

## ADC 캘리브레이션

- 조건: BT3을 누른 채 전원 인가 → OLED에 'CALIBRATION MODE ENABLED'
- 수행: 8채널 모두 9.00V 기준 전압 인가 후, BT3 3초 롱프레스 또는 CLI `cal`
- 결과: 채널별 게인 (0.8x~1.2x) 자동 계산 → Flash 저장
- 유효 범위: 입력 전압 8.5V ~ 9.5V
- 게인 수동 설정: HR 19~26에 직접 값 쓰기 가능 (1000 = 1.0x)

---

## 미구현 기능 (향후 펌웨어 업데이트 필요)

아래 기능은 [리얼시스 v0.2 요청서]에서 정의되었으나 현재 펌웨어에 미반영.

**Watchdog** 기능은 "Master 통신 이상 시 Slave 안전 동작 보장"의 핵심이므로 펌웨어 구현이 필요해 보임.

| 기능 | 설명 | 비고 |
|---|---|---|
| Watchdog (Heartbeat 감시) | Master Heartbeat 미갱신 시 자동 모드 전환 | MCG 소프트웨어로 대체 불가 — PCB가 자체 판단해야 함 |
| OP_MODE (운전 모드) | 비상정지/기본값 동작/자동제어 | HR 19~26이 ADC Gain으로 사용 중 — 주소 재배치 필요 |
| Flash 초기값 | 전원 재인가 시 PWM Duty/DOUT 복원 | 현재는 MCG 서비스 시작 시 write로 대체 |
| DOUT 전압 선택 | 12V/24V 선택 | 하드웨어 레벨 — 소프트웨어 불가 |
| S-Curve 시간 가변 | 램프 시간 설정 (0~100) | 현재 1초 고정 |
