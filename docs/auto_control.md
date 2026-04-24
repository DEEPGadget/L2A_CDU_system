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
| Pump L1 / L2 | — | 고정 `60 %` (NVIDIA DGX A100 최소 운용 40 % + 기동 여유 20 %, [UI.md](UI.md) 초기 Duty 값 참고). 독립 제어는 Stage 3에서 도입. |

**Fan lookup table** (L1/L2 공통 적용)

| outlet 온도 | Fan duty |
|---|---|
| < 30 °C | 20 % |
| 30 – 35 °C | 40 % |
| 35 – 40 °C | 60 % |
| ≥ 40 °C | 100 % |

- 구간 전이 **hysteresis ±1 °C** — 예: 35 °C 상향은 35.0에서, 하향은 34.0에서. ping-pong 방지.
- Hysteresis 상태는 루프별로 독립 보관 (L1의 구간 전이가 L2에 영향 없음).
- 임계치 상수는 [threshold.md](threshold.md)의 coolant temp warning/critical과 별도 (제어 vs 알람은 책임 분리).

**초기 구현 우선순위**: Stage 1만으로 Auto 모드 MVP 확보.

---

### Stage 2 — Outlet Temp PI 제어

**목적**: 부드러운 연속 제어. 열부하 변화(서버 GPU 사용률)에 적응.

**전제**: Stage 1이 현장에서 1주 이상 이슈 없이 동작 확인 후 진입.

**제어식**

```
error    = outlet_temp − setpoint
fan_pwm  = clamp(base_duty + Kp·error + Ki·∫error, 0, 100)
```

| 변수 | 초기값 | 비고 |
|---|---|---|
| `setpoint` | 40 °C | 서버 허용 outlet — 현장 튜닝 |
| `base_duty` | 40 % | 제어 작용 없을 때 정상 냉각 유지 듀티 |
| `Kp` | 5.0 | 1 °C 초과 시 +5 %P |
| `Ki` | 0.5 | 1 Hz 기준 — 현장 튜닝 |

**Pump**: 여전히 고정 60 %. (ΔT 기반 trim은 Stage 3로 이월.)

**라이브러리**: `simple-pid` (MIT, [m-lundberg/simple-pid](https://github.com/m-lundberg/simple-pid))
- `output_limits=(0, 100)` 설정 시 anti-windup 자동.
- `sample_time` 지원 — 호출 주기 흔들림에 강함.

---

### Stage 3 — Cascade (선택)

**목적**: 유량 변동이 제어 품질을 해칠 때 Pump도 제어 루프에 편입.

**구조**
- **외부 루프** (느림): `ΔT = outlet − inlet` → pump duty PI. 목표 ΔT 예: 10 °C.
- **내부 루프** (빠름): outlet setpoint → fan duty PI (= Stage 2).

**적용 조건**
- Stage 2 운영 중 유량 drift로 outlet 제어 품질이 악화될 때만.
- 튜닝 공수 약 2배. Stage 2로 충분하면 skip.

---

## 3. 공통 가드레일

모든 Stage 공통으로 적용. 라이브러리 선택과 무관하게 호출부에서 보장해야 함.

### Rate limiting
- duty 변화율 **≤ 5 %/s** — 기계 수명, 유체 망치 현상(water hammer), RPM 피드백 노이즈 완화.
- 구현: `new_duty = clamp(target, prev_duty − 5, prev_duty + 5)` (1 Hz 호출 기준).

### Hysteresis (Stage 1)
- Fan curve 구간 경계에 **±1 °C dead-band** — §2 Stage 1 표 설명 참고.

### Anti-windup (Stage 2, 3)
- Integrator가 output clamp에 걸린 상태에서 `∫error` 누적 중단.
- `simple-pid`는 `output_limits` 설정 시 자동 처리.

### Bumpless transfer (Manual ↔ Auto 전환 시)
- Auto 진입 순간 PI 내부 상태를 현재 실제 duty로 초기화해서 step change 방지.
- 구현: `pid.set_auto_mode(True, last_output=current_pwm)`.
- Manual로 나갈 때는 별도 처리 불필요 (사용자 입력이 PI 출력을 덮어씀).

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
| [lm-sensors/lm-sensors](https://github.com/lm-sensors/lm-sensors) `fancontrol` | Trip-point 기반 fan curve, hysteresis, min/max 클램프 구조 | Stage 1 |
| [m-lundberg/simple-pid](https://github.com/m-lundberg/simple-pid) | PI 라이브러리 — anti-windup, `output_limits`, `sample_time`, `set_auto_mode` | Stage 2, 3 |
| [kennycoder/waku-ctl](https://github.com/kennycoder/waku-ctl) | Rate limiting (step up/down duration), delta temp 계산, PWM+RPM 피드백 루프 구조 | 전 Stage 공통 |

### 검토했으나 미채택

| 출처 | 미채택 사유 |
|---|---|
| [TUMFTM/sim_VTMS](https://github.com/TUMFTM/sim_VTMS) | MATLAB/Simulink 기반 EV 열관리 **시뮬레이터**. 제어 알고리즘 레시피 없음 — 추후 오프라인 튜닝용 플랜트 모델 필요 시 재검토 |
| [openhp/HeatPumpController](https://github.com/openhp/HeatPumpController) | 히트펌프 state machine + 릴레이 on/off + EEV 스테퍼. CDU의 **연속 PWM 변조** 모델과 제어 철학이 다름 |

### 도메인 참고

- **ASHRAE TC 9.9** Liquid Cooling guidelines — 데이터센터 ΔT 권장치(10–14 °C), 공급온도 setpoint 설정 기준. (공식 문서 유료)
- [Grundfos — IT Cooling](https://www.grundfos.com/solutions/industries/industrial-manufacturing-oems/it-cooling) — delta-T 기반 VFD 펌프 제어 개념.
- [Modelon — Simulating Coolant Distribution Units](https://modelon.com/blog/simulating-coolant-distribution-units/) — 1차/2차 루프 모델 구성, PID 안정/불안정 구성 비교.
- [Real-time optimization of the liquid-cooled data center](https://www.sciencedirect.com/science/article/abs/pii/S0306261924004847) — cold plate 기반 실시간 최적화 접근 논문.
