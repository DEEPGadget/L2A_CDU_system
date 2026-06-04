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

Rev_C 부터 **유량 센서 4개 (병렬 분기당 1개, 루프당 2개)** 도입. [src/mcg/polling.py](../src/mcg/polling.py) `_read_flow_lpm()` 가 IR 32~35(ADC 전압 4ch)을 읽어 **루프별로 2개를 합산** → `sensor:flow_rate_1/2` 로 publish. 유량은 **실측값**이며 펌프 추정이 아님 — 센서 미가용 시 미발행(아래 참고).

### 실 센서: SIKA **VVX15** × 4 (Vortex) — Analogue 전압 출력 방식

카탈로그 수령 (docs/private/Flowmeter spec.pdf). **모델 = VVX15 로 통일** (인증·양산 동일). 각 루프의 **병렬 펌프 2 분기에 센서 1개씩 = 루프당 2개 = 총 4개**. 실물 미도착 — 결선·환산은 아래대로 진행, 실물 도착 후 `_FLOW_SENSOR_ENABLED` 토글.

> **측정 방식 = Analogue 전압 출력 (각 센서 Pin 2, 0.5~3.5 V).** Frequency 대신 **ADC 전압 입력(AIN1~4)** 사용. 풀업·타이머 채널 불필요 → 센서당 3선 (전원+신호).
>
> **루프 유량 = 두 분기 센서의 합.** Loop1 = AIN1 + AIN2, Loop2 = AIN3 + AIN4. (병렬 분기 각각 ~절반 유량 → 합 = 루프 총유량. 단일 펌프 ~35 LPM × 2 = 루프 ~70 LPM.)

#### Input / Output 요약 (센서 1개 기준)

| 구분 | 핀 | 내용 |
|---|---|---|
| **Input (전원)** | Pin 1 = +U_B | **+12 V** (8~30 V 범위, 12 V 정상 동작) |
| | Pin 3 = GND | 전원·신호 공통 기준 |
| **Output (유량)** | Pin 2 = U_Flow | 아날로그 전압 **0.5~3.5 V** (유량 선형 비례) |
| 미사용 | Pin 4, 5 | Frequency / 온도용 — 미결선 |

> Pin 1(전원)은 **필수**. 센서는 능동 소자(소비전류 <15 mA)라 +U_B 없으면 Pin 2 에 출력 없음. Pin 3(GND)는 전원·신호 겸용.

#### 환산 (VVX15 통일, 0.5~3.5 V 선형)

| 항목 | VVX15 |
|---|---|
| 모델 | VVX15 (DN15, G¾) |
| 센서당 유량 범위 | 2 ~ 40 L/min |
| 출력 스케일 | 0.5 V=2 / 3.5 V=40 LPM |
| rate | 0.07895 V/(L/min) |
| **센서 환산식** | `branch_lpm = 12.667 × V − 4.333` (0 미만 clamp) |
| **루프 유량** | `loop_lpm = branch_a + branch_b` (루프당 2~80 LPM) |

> 참고(미사용): VVX20 = `25 × V − 7.5` (0.5 V=5 / 3.5 V=80). 현재 `_FLOW_MODEL="VVX15"` 단일.

**M12 핀맵 (VVX 4-pin, 센서당 동일) — Spec PDF p.9 "Pin assignment" / p.9~10 "Flow U_Flow" 도식**
- Pin 1: +U_B (전원) / Pin 2: U_Flow (0.5~3.5 V) / Pin 3: GND / Pin 4, 5: 미사용

**MCS_IO 결선 (4 센서)**
- 각 VVX Pin 1 → +12 V (fuse 권장), Pin 3 → GND (PCB GND 공통)
- VVX Pin 2 → ADC 전압 입력:
  - **AIN1 = CH1 = IR 32**, **AIN2 = CH2 = IR 33** → **Loop1** (합산)
  - **AIN3 = CH3 = IR 34**, **AIN4 = CH4 = IR 35** → **Loop2** (합산)
- 단위 0.01 V (350 = 3.50 V). 환산: `branch_lpm = max(0, 12.667 × (IR/100) − 4.333)`, `loop_lpm = branch_a + branch_b`

**발행 Redis 키 (총합 + 4분기)**: 루프 총합 `sensor:flow_rate_1/2` + 분기별 `sensor:flow_rate_1_1`(AIN1), `_1_2`(AIN2), `_2_1`(AIN3), `_2_2`(AIN4). UI(Local 도식·Web 카드)는 **총합(큰글씨) + 분기 1/2(작은글씨)** 표시, History 는 `sensor_flow_rate_branch{loop,branch}` Prometheus 메트릭.

> **도식 위치**: 유량계는 **outlet manifold ↔ fan+radiator 사이**(귀환선)에 표시. 물리적으로 outlet 에서 2분기로 갈라져 각 분기에 센서 1개씩(=fan+radiator 4 라인) 이지만, UI 도식은 2 유로를 하나로 합쳐 루프당 박스 1개로 표시 ([cooling_health.svg](../src/local_ui/assets/cooling_health.svg)).

> ⚠ **ADC 입력 범위 / 분해능 (실물 검증 시 확인)**
> PCB ADC 채널은 0~12 V 범위(12-bit, 4095 count). 0.5~3.5 V 신호는 범위의 ~29 %만 사용 → span 75 L/min ≈ 1024 count → 분해능 ≈ 0.073 L/min/count (충분). 최대 출력 3.5 V < ADC 상한 12 V → 클리핑 없음, 분압기 불필요.
> ADC 게인 캘리브레이션이 9 V 기준이므로 저전압 구간(0.5~3.5 V) 정확도는 실물 도착 후 검증 권장.

### 펌프 배치 (L2A Rev_C)

- 병렬 2개씩 × 병렬 2 루프 = 총 4 펌프 (HR 8~11 = 펌프 CH9~12, TIM8 @ 1 kHz)
- 한 루프 = 병렬 2펌프 → 동일 head (≈130 kPa), **루프 유량 = 단일 펌프 × 2**
- 시스템 max = flow_L1 + flow_L2 (참고용, UI 미표시)

### UI / MCG duty 매핑

펌프의 **사용구간 17~85 % PWM** (Pump spec 4.2.1: 17 %=Nmin, 85 %=Nmax 선형 상한) 을 UI 0~100 % 에 매핑한다. 단 **UI 0 % = 정지**: 펌프 spec 의 8~13 % 정지밴드(n=0) 안의 **12 % PWM** 을 보내 정지시킨다. 구현: [src/mcg/duty_mapper.py](../src/mcg/duty_mapper.py) `ui_to_pump_hr()`.

```
UI 0      → HR 120 (12 %, 정지)
UI (0,100] → HR = round((17 + 0.68 × ui) × 10)  clamp [170, 850]   # 17~85 % 선형
```

| UI duty | pump_input PWM | 비고 |
|---:|---:|---|
| 100 % | 85 % | Nmax |
|  60 % | 57.8 % | (Auto 기본 fixed duty) |
|  50 % | 51.0 % | |
|   1 % | 17.7 % | ≈ Nmin |
| **0 %** | **12 %** | **정지 (n=0)** |

**UI 하한 없음**: 0 = 정지가 유효값. Fan 은 무관(UI 0~100 → 0~100 직접, 운용 하한 10 %).

> ### ✅ 과거 "UI 0 % bypass hazard" 해소
>
> 이전 `0.85 × ui` 매핑은 `ui=0 → pump_input 0 %` 가 되어 Pump spec **0~8 % = Nmax safety fallback** 을 trigger(정지 의도인데 풀가동) 하는 약점이 있었다. 신 매핑은 **UI 0 → 12 % (명시적 정지밴드)** 로 보내므로 0 이 어느 경로로 들어와도 **풀가동이 아니라 정지**한다 — hard clamp 의 하한이 곧 stop 값(120)이라 우회 위험 자체가 없어짐.
>
> ⚠ **Auto 모드 주의**: pump fixed duty 를 0(정지) 으로 두면 Auto 냉각 중 펌프가 멈춘다 — 코드로 막지 않으니 운용 상 주의.

Pump spec 4.2.1 동작 구간 (참고):
- 0~8 % : Nmax 풀가동 (안전 트리거)
- **8~13 % : 정지 (n=0)** ← UI 0 % 가 보내는 12 % 가 여기
- 13~17 % : Nmin
- **17~85 % : Nmin ~ Nmax 선형** ← UI 1~100 % 가 닿는 영역
- 85~95 % : Nmax 포화 / 95~100 % : no use

### 유량 = 실 센서 측정값 (펌프 추정 폐기)

유량은 **실 센서(SIKA VVX 아날로그 전압)로 측정한 값**이며, **펌프 duty 로부터 추정하지 않는다.** 센서 미가용(`_FLOW_SENSOR_ENABLED` off 또는 read 실패) 시 MCG 는 `sensor:flow_rate_*` 를 **발행하지 않으며**, UI 는 마지막 값 또는 no-data("--") 를 표시한다 (조작된 추정치를 만들지 않음).

> 과거에는 센서 hook 이 비기 전까지 `flow_loop_lpm = 70 × (ui_duty/100)` 펌프-추정 fallback 을 publish 했으나, 유량을 실측값으로 일원화하면서 **제거함** ([polling.py](../src/mcg/polling.py) `_read_flow_lpm()`).

#### 유량 기준(reference)과 VVX15 마진

**왜 펌프 스펙만으로 실유량을 모르나**: 펌프 P-Q 곡선(Pump spec.pdf §2.3: 12V 100% 정격 45 LPM @130 kPa, 자유유량 ~67 LPM)은 펌프의 *능력*이고, 실제 유량은 **펌프 곡선 ∩ 시스템 저항 곡선**의 교점에서 결정된다. 시스템 저항이 크면 저유량(~35), 작으면 고유량(~67쪽). 시스템 곡선을 정확히 모르므로 **실유량은 스펙만으로 확정 불가 — 그래서 VVX15 로 실측한다.**

**설계 기준 (추정치)**: 100% 가동(Nmax) 시 **루프 ≤ 70 LPM, 분기당 ≤ 35 LPM** 을 명목 상한으로 채택 (병렬 2 펌프, 시스템 저항 ~130 kPa 가정).

**VVX15 마진 / bring-up 게이트**: VVX15 측정 상한 = **40 LPM/센서**. 분기 설계상한 35 와의 마진은 ~14 % 로 얇다. 펌프 정격 곡선상 분기는 최대 45(정격)~67(자유유량) 까지 가능하므로, **시스템 저항이 가정보다 작으면 분기 실유량이 40 을 넘어 VVX15 가 포화(3.5V clip)** 될 수 있다.
> ⚠ **bring-up 안전 게이트**: 실물 첫 측정에서 각 분기 유량이 **≤ 40 LPM** 인지 확인. 초과하면 (a) 시스템 저항 추가, (b) 운용 PWM 상한 하향, 또는 (c) 센서 모델 상향(VVX20=80 LPM) 재검토. polling 은 분기당 0 미만 clamp 만 하고 상한 clip 은 센서 HW 특성에 위임.

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
