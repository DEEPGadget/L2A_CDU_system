# PCB (Modbus Slave) — MCS_IO Board REV_C

> 본 문서는 **MCS_IO Board REV_C (= LTS v1)** 기준이다. 다음 revision 은 **REV_D (= LTS v2)** 가 될 예정 — 사양 확정 시 별도 문서로 분리. 버전 정책은 [ARCHITECTURE.md §7 "Versioning (LTS policy)"](../ARCHITECTURE.md) 참고.

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
| 0~3 | PWM Duty | **펌프** CH1~4 듀티비 (L2A Rev_C: 미사용. 펌프는 CH 9~12 = HR 8~11. 변형별 매핑은 MCG.md §10.2 참고) | 0~1000 (0.0~100.0%) |
| 4~11 | PWM Duty | **팬** CH5~12 듀티비 | 0~1000 (0.0~100.0%) |
| 12 | PWM Freq (TIM1) | CH1~4 주파수 (L2A Rev_C: 미사용 채널이므로 영향 없음. 변형별 매핑은 MCG.md §10.2 참고) | 1000~25000 Hz |
| 13 | PWM Freq (TIM2) | CH5~8 주파수 (L2A Rev_C: 팬, 운용 기본 **25000 Hz**) | 1000~25000 Hz |
| 14 | PWM Freq (TIM8) | CH9~12 주파수 (L2A Rev_C: 펌프, 운용 기본 **1000 Hz** — MCG 시작 시 명시 write) | 1000~25000 Hz |
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
| 13~24 | Pulse Freq | 펄스 주파수 12채널 (팬 RPM 피드백; **RPM = Hz × 30**, 2 pulse/rev). ※ L2A Rev_C 운용: 팬 RPM 4 채널 = CH 5~8 = IR 17~20, MCG 가 loop 별 2ch 평균을 `sensor:fan_rpm_1/2` 로 publish. 펌프 (CH 9~12) 는 Tach 미사용 | 0~65535 Hz |
| 25 | DIN Status | 디지털 입력 DIN1~6 | bit0~5 |
| 26 | Pulse State | 펄스 핀 H/L 상태 | bit0~11 |
| 27 | DIP Switch | DIP 스위치 1~6 | bit0~5 |
| 28 | NTC Temp | **T1 = Inlet  L1** (NTC CH13) | 0.1°C signed (253 = 25.3°C, 0xFE6C = -40.4°C open) |
| 29 | NTC Temp | **T2 = Outlet L1** (NTC CH14) | 0.1°C signed |
| 30 | NTC Temp | **T3 = Outlet L2** (NTC CH15) | 0.1°C signed |
| 31 | NTC Temp | **T4 = Inlet  L2** (NTC CH16) | 0.1°C signed |

> Pin map matches the PCB silkscreen order T1/T2/T3/T4 = inlet/outlet/outlet/inlet (the T2/T3 outlets sit between the two inlets so a single thermistor bundle can be routed straight). Open-circuit returns -40.4 °C (NTC measurement-range floor).
| 32~39 | Voltage | 전압 (CH1~8) — 현재 전부 미사용(예약) | 0.01V (900=9.00V) |

> ΔT 계산: `ΔT_Lx = outlet_Lx − inlet_Lx`

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

## 유량 추정

Rev_C 부터 **각 루프 합류점에 실 유량 센서 1개씩 (총 2개)** 도입 예정. 채널/환산 계수 확정 시 [src/mcg/polling.py](../src/mcg/polling.py) `_read_flow_lpm()` hook 을 채워 `sensor:flow_rate_1/2` 로 publish. 그 전까지는 아래 derived fallback 동작.

### 실 센서: SIKA **VVX20** (Vortex)

카탈로그 수령 (docs/private/Flow meter spec1.pdf, spec2.pdf). **발주 모델 = VVX20 확정**. 실물 미도착 — 결선·환산은 아래대로 진행, 실물 도착 후 `_FLOW_SENSOR_ENABLED` 토글.

| 항목 | 값 |
|---|---|
| 모델 | **VVX20** (DN20, G1) |
| 유량 범위 | 4 ~ 80 L/min |
| Pulse rate | **200 pulses/L** |
| F_max (정격 상한) | 80 × 200 / 60 ≈ **267 Hz** |
| F at 4 L/min | 4 × 200 / 60 ≈ 13.3 Hz |
| 환산식 | `flow_lpm = Hz × 60 / 200 = Hz × 0.3` |

PCB 펄스 입력 한계 (0~10 kHz) 대비 1/37 수준 → **Frequency 출력 + 펄스 입력 채널** 조합이 최적 (아날로그 대비 분해능·노이즈 우위).

**M12 핀맵 (VVX 4-pin)** — Spec PDF 3.1.1 참조
- Pin 1: +UB (8~30 V DC, Push-Pull/NPN/PNP 시)
- Pin 3: GND
- Pin 4: Frequenz (Push-Pull / NPN OC / PNP OC 중 발주 시 택1)

**MCS_IO 결선 권장**
- VVX Pin 1 → +24 V (펌프 전원 라인에서 분기, fuse 권장)
- VVX Pin 3 → GND (PCB GND 공통)
- VVX Pin 4 → 펄스 입력 **CH1 (L1)** / **CH2 (L2)** — Fan tach가 CH5~8 점유, CH1~4 가용
- Modbus 읽기 주소: **IR 13 (CH1, L1), IR 14 (CH2, L2)** — 단위 Hz
- 환산: `flow_lpm = Hz × 60 / pulses_per_liter`

> ⚠ **펄스 입력 전압 레벨 미확인 (현장 검증 필요)**
> MCS_IO 매뉴얼에 펄스 입력단의 허용 전압 레벨이 명시되지 않음. STM32G474 GPIO는 5 V tolerant 이나 PCB 입력단에 전치 보호회로가 있을 수 있음. VVX Push-Pull은 +UB 그대로 출력 → 24 V 공급 시 24 V 펄스가 PCB 입력으로 들어감.
> **확인 전까지 NPN Open Collector + PCB 측 5 V 풀업** 구성을 권장 (R_L ≈ 5 kΩ, Spec PDF *3 권장). 이렇게 하면 펄스 진폭이 PCB 로직 레벨로 클램프됨.

> ⚠ **출력 옵션 (Push-Pull vs NPN OC) 발주 시 확정 필요**. 4-pin 케이블이면 Pin4가 펄스 출력. 5-pin이면 Pin5에 온도(Pt1000/NTC) 동시 출력도 가능 (이 경우 NTC 채널 IR 28~31 의 외기 슬롯 활용 가능, 단 매핑 추가 필요).

### 펌프 배치 (L2A Rev_C)

- 병렬 2개씩 × 병렬 2 루프 = 총 4 펌프 (HR 8~11 = 펌프 CH9~12, TIM8 @ 1 kHz)
- 한 루프 = 병렬 2펌프 → 동일 head (≈130 kPa), **루프 유량 = 단일 펌프 × 2**
- 시스템 max = flow_L1 + flow_L2 (참고용, UI 미표시)

### UI / MCG duty 매핑

UI 도메인은 사용자 직관 (UI X% = pump 출력 X% 의 일정 비율) 을 유지하기 위해 **직접 비례 매핑**. UI 0% = 펌프 정지. 단 UI 100% 가 곧 pump_input 100% 로 가지 않도록, **UI 100% → pump_input 85%** (Pump spec 4.2.1 의 운용 상한) 로 캡:

```
pump_input_pwm = 0.85 × ui_duty
```

| UI duty | pump_input PWM | flow (loop, 병렬 ×2) |
|---:|---:|---:|
| 100 % | 85 % | 70.0 LPM |
|  75 % | 63.75 % | 52.5 LPM |
|  50 % | 42.5 % | 35.0 LPM |
|  **20 %** (UI 하한) | **17 %** (Nmin) | 14.0 LPM |
|   0 % | 0 % | 0 LPM (정지) |

**UI 입력 하한 = 20 %**: pump spec 4.2.1 의 운용 하한 17 % (Nmin) 가 위 매핑으로 UI 20 % 에 대응 (`17 / 0.85 ≈ 20`). UI 도메인에서 20 % 미만 입력은 펌프가 정지·Nmin 사이 회피 구간으로 들어가므로 거부. Auto 모드 (PI) 의 `out_min` 도 동일 하한을 강제.

> ### ⚠ Hazard — UI 0 % bypass risk (현재 무해, 향후 네트워크 노출 시 발생 가능)
>
> 직접 비례 매핑 `pump_input = 0.85 × ui_duty` 의 약점: **ui_duty = 0 → pump_input = 0** 이 되는데, Pump spec 4.2.1 에 따르면 pump_input **0~8 % 구간은 "Nmax safety full-speed (PWM 신호 이상 fallback)"** trigger 다. 즉 사용자는 "정지" 의도이나 펌프는 풀가동.
>
> | UI duty | pump_input | spec 해석 | 실제 동작 |
> |---:|---:|---|---|
> | 100 % | 85 % | Nmax 포화 | 정격 풀가동 (OK) |
> |  20 % | 17 % | Nmin | 최저속 (OK) |
> | **0 %** | **0 %** | **0~8 % Nmax safety fallback** | **펌프 풀가동 (예상과 반대)** |
>
> **현재는 무해**: PySide6 Local UI 가 유일한 entry point 이며, `NumpadDialog` + Settings 가 모두 하한 20 % 를 강제 ([src/local_ui/widgets/control_panel.py](../src/local_ui/widgets/control_panel.py) `min_value`). UI 외 경로로 `sensor:pump_pwm_duty_*` 에 0 이 들어올 가능성 없음.
>
> **향후 네트워크 노출 시 위험**: Web UI (REST API), 원격 MCG 명령, 외부 자동화 스크립트 등이 추가되어 `sensor:pump_pwm_duty_*` redis 키에 직접 SET 할 수 있게 되면 UI 의 하한 강제를 우회할 수 있다.
>
> **권장 mitigation** (MCG 구현 시 적용):
> 1. **MCG 단의 hard clamp**: PCB HR write 직전에 `hr_value = max(170, min(850, round(0.85 * ui_duty * 10)))` 로 강제. UI domain 무관 안전 보장.
> 2. **0 입력 special-case**: `ui_duty == 0` 일 때 pump_input 을 10 % (8~13 % 정지 구간 중심) 로 매핑하여 "OFF" 의도 보존.
> 3. **API 레벨 validation**: REST API endpoint 도입 시 input schema 에 `min: 20, max: 100` 강제.
>
> 위 1~3 은 MCG 가 실제 구현되는 시점에 [auto_control.md](auto_control.md) 의 가드레일 정책과 함께 일관 적용해야 한다.

Pump spec 4.2.1 동작 구간 (참고):
- 0~8 % : Nmax 풀가동 (안전 트리거)
- 8~13 % : 정지
- 13~17 % : Nmin
- **17~85 % : Nmin ~ Nmax 선형** ← 위 매핑이 닿는 영역
- 85~95 % : Nmax 포화 / 95~100 % : no use

### 유량 산정 (실 센서 hook 비어 있을 때의 fallback)

시스템 손실 마진 포함:

```
flow_loop_lpm = 70 × (ui_duty / 100)        # 루프당 max 70 LPM (병렬 펌프 P1‖P2)
```

단일 펌프 (단독, 12V PWM 100%) 정격점 45 LPM — 시스템 저항 고려해 35 LPM 채택. UI 100 % 일 때 pump_input 85 % 로 운용하므로 정격(100 %) 대비 ~94 % 의 유량 ≈ 42 LPM 이 spec 상 예상치이나 **시스템 저항 보수 마진** 으로 35 LPM 채택. **병렬 2 펌프 → 루프당 70 LPM** (head 는 단일 펌프와 동일).

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
