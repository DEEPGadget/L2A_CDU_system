# Auto Control Algorithm

> Auto 모드에서 MCG 메인 루프가 Polling 직후 호출하여 Pump/Fan PWM duty를 결정하는 알고리즘의 설계 문서.
> MCG 서비스 명세는 [MCG.md](MCG.md) 참고.

---

## 1. 개요

| 항목 | 내용 |
|---|---|
| **호출 시점** | 메인 루프 cycle에서 Polling 이후 ([MCG.md §4](MCG.md#4-메인-루프) step 5) |
| **주기** | 1 Hz (메인 루프 cycle) |
| **입력** | 냉각수 inlet/outlet 온도 (L1/L2), 유량 (L1/L2), 현재 Pump/Fan PWM duty |
| **출력** | 새 Pump/Fan PWM duty (0–100 %) → Modbus Write |
| **적용 범위** | L1/L2 독립 + 동일 알고리즘 대칭 (초기). 실측 후 비대칭 허용 여부 재검토 |

> 공유 센서(Reservoir level·pH·전도도, Ambient temp·humidity)는 양 루프 공통 읽기. Auto 제어 입력에는 직접 사용하지 않음 (알람 전용).

---

## 2. 단계적 도입

로드맵. 한 단계씩 안정화 후 다음으로 진행.

### Stage 1 — Fan curve + 고정 Pump (baseline)

**목적**: 알람·통신·UI 등 주변 시스템이 안정화될 때까지 deterministic한 제어 확보. 디버깅 쉬움, 모든 입출력이 예측 가능.

**L1 / L2 독립 제어**: 양 루프의 outlet 온도 센서가 각각 독립적으로 모니터링되므로, fan도 자기 루프의 outlet만 보고 결정. 더 뜨거운 루프는 자연스럽게 더 많이 식혀짐.

| 액추에이터 | 입력 | 결정 방식 |
|---|---|---|
| Fan L1 | `sensor:coolant_temp_outlet_1` | 아래 lookup (독립) |
| Fan L2 | `sensor:coolant_temp_outlet_2` | 아래 lookup (독립, 동일 테이블) |
| Pump L1 / L2 | — | 고정 `60 %`. 독립 제어는 Stage 3에서 도입. |

> **Pump 60% 근거**: Vertiv CoolChip CDU100 공식 하한 15% (motor cooling, 기본 flow/DP 확보), Grundfos/업계 VFD 최소 30% of BEP 권고 대비 안전 마진 충분. NVIDIA DGX A100 최소 운용 40% + 기동 여유 20%도 함께 만족. 완전 정지는 센서 feedback 붕괴·stagnation·응결·재기동 지연 때문에 금지 ([§5 참고자료](#5-참고자료)).

**Fan lookup table** (L1/L2 공통 적용)

| outlet 온도 | Fan duty | 근거 |
|---|---|---|
| < 30 °C | **20 %** | idle floor. 베어링 상시 회전, load spike 즉응성, waku-ctl 하한과 정합 |
| 30 – 40 °C | **40 %** | Stage 2 `base_duty`와 일치, 정상 열부하 냉각 |
| 40 – 50 °C | **65 %** | Stage 2 setpoint(40 °C) 초과분에 대한 램프 |
| 50 – 60 °C | **85 %** | Outlet warning(60–65 °C) 진입 직전 여력 확보 |
| ≥ 60 °C | **100 %** | Outlet alarm 경계, 가용 냉각 최대화 |

- 구간 전이 **hysteresis ±1 °C** — 예: 40 °C 상향은 40.0에서, 하향은 39.0에서. ping-pong 방지.
- Hysteresis 상태는 루프별로 독립 보관 (L1의 구간 전이가 L2에 영향 없음).
- 제어 임계치와 [threshold.md](threshold.md)의 알람 임계치는 별도 (제어 vs 알람은 책임 분리). 제어 테이블 상한(100% 도달점)은 알람 warning 경계와 정합시킴.
- Fan 완전 정지는 안 함. Idle 상태에서도 20% 하한 유지 ([§3 Minimum duty floor](#minimum-duty-floor)).

**초기 구현 우선순위**: Stage 1만으로 Auto 모드 MVP 확보.

---

### Stage 2 — Outlet Temp PI 제어

**목적**: 부드러운 연속 제어. 열부하 변화(서버 GPU 사용률)에 적응.

**전제**: Stage 1이 현장에서 1주 이상 이슈 없이 동작 확인 후 진입.

**제어식**

```
error    = outlet_temp − setpoint
fan_pwm  = clamp(base_duty + Kp·error + Ki·∫error, 20, 100)
```

| 변수 | 초기값 | 비고 |
|---|---|---|
| `setpoint` | 40 °C | Stage 1 lookup의 정상 구간 상한과 정합. 현장 튜닝 |
| `base_duty` | 40 % | 제어 작용 없을 때 정상 냉각 유지 듀티 (Stage 1 lookup 30–40 °C 구간과 일치) |
| `output_limits` | `(20, 100)` | 하한 20% = idle floor (Stage 1과 동일 정책). 0% 허용 안 함 |
| `Kp` | 5.0 | 1 °C 초과 시 +5 %P |
| `Ki` | 0.5 | 1 Hz 기준 — 현장 튜닝 |

**Pump**: 여전히 고정 60 %. (ΔT 기반 trim은 Stage 3로 이월.)

**라이브러리**: `simple-pid` (MIT, [m-lundberg/simple-pid](https://github.com/m-lundberg/simple-pid))
- `output_limits=(20, 100)` 설정 시 anti-windup 자동 + 하한 floor.
- `sample_time` 지원 — 호출 주기 흔들림에 강함.

---

### Stage 3 — Cascade (선택)

**목적**: 유량 변동이 제어 품질을 해칠 때 Pump도 제어 루프에 편입.

**구조**
- **외부 루프** (느림): `ΔT = outlet − inlet` → pump duty PI. 목표 ΔT 10–14 °C (ASHRAE TC 9.9 권장 범위).
- **내부 루프** (빠름): outlet setpoint → fan duty PI (= Stage 2).

**Pump output_limits**: `(30, 100)` — Grundfos/VFD 업계 30% of BEP 하한, Vertiv CDU100 공식 15% 하한 + 안전 마진. 0% 금지.

**적용 조건**
- Stage 2 운영 중 유량 drift로 outlet 제어 품질이 악화될 때만.
- 튜닝 공수 약 2배. Stage 2로 충분하면 skip.

---

## 3. 공통 가드레일

모든 Stage 공통으로 적용. 라이브러리 선택과 무관하게 호출부에서 보장해야 함.

### Rate limiting
- duty 변화율 **≤ 5 %/s** — 기계 수명, 유체 망치 현상(water hammer), RPM 피드백 노이즈 완화.
- 구현: `new_duty = clamp(target, prev_duty − 5, prev_duty + 5)` (1 Hz 호출 기준).

### Minimum duty floor
- **Fan 하한 20%**, **Pump 하한 30%** (Stage 3 기준, Stage 1·2는 pump 60% 고정이라 자연 충족).
- Lookup/PI 출력 위에 **하드 clamp**를 한 번 더 적용 — 제어 로직 버그로 floor 아래로 내려가도 HW 측 방어.
- 근거: 모터 자가냉각(TEFC), 유량/dP 센서 feedback 유지, stagnation·응결·바이오필름 방지, 재기동 kick-start 회피, load spike 즉응성.
- **예외**: Emergency(비상정지) 시 duty = 0 강제 ([§Emergency 우선](#emergency-우선)).

### Hysteresis (Stage 1)
- Fan curve 구간 경계에 **±1 °C dead-band** — §2 Stage 1 표 설명 참고.

### Anti-windup (Stage 2, 3)
- Integrator가 output clamp에 걸린 상태에서 `∫error` 누적 중단.
- `simple-pid`는 `output_limits` 설정 시 자동 처리.

### Bumpless transfer (Manual ↔ Auto 전환 시)
- Auto 진입 순간 PI 내부 상태를 현재 실제 duty로 초기화해서 step change 방지.
- 구현: `pid.set_auto_mode(True, last_output=current_pwm)`.
- Manual로 나갈 때는 별도 처리 불필요 — 사용자 첫 입력 전까지 PCB는 마지막 Auto PWM을 유지 (MCG Manual은 큐 입력이 있을 때만 Write).

### Emergency 우선
- 비상정지 조건 ([MCG.md §5](MCG.md#5-상세) 알람 검사) 충족 시 PI/lookup 출력 무시, duty = 0 강제.
- 비상 해제 시 Auto 자동 재진입 금지 — Manual 경유하여 운영자 확인 후 재진입.
- 비상정지 상세는 시스템 안정화 후 설계 (MCG.md TODO).

---

## 4. L1 / L2 적용

- 각 루프에 **독립 알고리즘 인스턴스** (Stage 1: 독립 lookup state, Stage 2: 독립 PI object).
- **동일 파라미터 대칭** 시작 — 구조적으로 같은 두 루프를 구분하지 않음.
- 현장 실측에서 L1/L2 비대칭(예: 서버 발열 차이, 배관 압력 차이)이 확인되면 루프별 게인 허용. 그 전까지는 한 곳만 튜닝하고 복제.

---

## 5. 참고자료

### 빌려온 패턴

| 출처 | 차용 내용 | 적용 Stage |
|---|---|---|
| [lm-sensors/lm-sensors](https://github.com/lm-sensors/lm-sensors) [`fancontrol`](https://github.com/lm-sensors/lm-sensors/blob/master/doc/fancontrol.txt) | Trip-point fan curve, `MINPWM`/`MINSTOP`/`MINSTART` kick-start 패턴, hysteresis, min/max clamp 구조 | Stage 1 |
| [m-lundberg/simple-pid](https://github.com/m-lundberg/simple-pid) | PI 라이브러리 — anti-windup, `output_limits`, `sample_time`, `set_auto_mode` (bumpless) | Stage 2, 3 |
| [kennycoder/waku-ctl](https://github.com/kennycoder/waku-ctl) | **최소 duty 하한 20% 강제** (PID `SetOutputLimits(min_duty, 255)`, `min_duty=51/255`), rate limiting, PWM+RPM 피드백 루프 | 전 Stage 공통 |

### 최소 duty / idle 거동 근거

| 출처 | 수치 / 내용 |
|---|---|
| [Vertiv CoolChip CDU100 Installation Guide](https://www.vertiv.com/4aaecd/globalassets/shared/vertiv-coolchip-cdu100-installation-and-commissioning-guide-sl-71337.pdf) | **Pump 최소 15%** 공식 명시 (motor fan cooling, 기본 flow/DP 확보). 0% 완전 정지는 수동 override에서만 허용. |
| [CSE — Designing for Minimum Flow With VFD Operation](https://www.csemag.com/your-questions-answered-designing-for-minimum-flow-with-vfd-operation/) | VFD 펌프 최소 속도 **30% of BEP**(업계 통념), 모델에 따라 15–50%. |
| [Modelon — Simulating CDU](https://modelon.com/blog/simulating-coolant-distribution-units/) | 저부하에서 "펌프 속도를 낮추되 정지는 안 함". 정체 시 1차측 온도 oscillation, PID 튜닝으로 완화. |
| lm-sensors `fancontrol` | `MINPWM`=0이면 팬 off, `MINSTOP`(pwmconfig 기본 ≈39%)으로 상시 회전 유지 선택 가능. 재기동 시 `MINSTART`(기본 ≈59%) kick-start. |

### 도메인 참고

- **ASHRAE TC 9.9** Liquid Cooling guidelines — 데이터센터 ΔT 권장치 **10–14 °C** (Stage 3 pump PI setpoint 근거). 공식 문서 유료.
