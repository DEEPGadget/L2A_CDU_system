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
| 해상도 | 720 × 1280 px (portrait) / **1280 × 720 px (landscape) — 운용 화면** |
| 회전 설정 | cmdline.txt `video=DSI-1:720x1280M@60,rotate=90` |

### ⚠ Layout 검증 체크리스트 (PySide6 신규/수정 시 필수)

**과거 반복 실수**: 신규 페이지 / 새 위젯 / 기존 위젯 항목 추가 시 1280×720 한계를 무시한 채 가로 overflow (오른쪽 넘침) 가 반복 발생함. 사용자가 직접 확인 시점에 발견. 아래 4단계 검증을 반드시 통과한 뒤에만 사용자에게 보고할 것.

1. **본 표 다시 확인**: 운용 화면 폭 **1280 px**, 높이 **720 px**, top_bar 64 px 고정 → 페이지 영역 = **1280 × 656 px**
2. **명시적 크기 강제**: 최상위 페이지/오버레이는 `setFixedSize` 또는 `setMaximumWidth(1280)`. status_strip 같은 고정 높이 위젯은 `setFixedHeight` 만 두고 가로는 부모 layout 에 위임 (단, contentsMargins + spacing + 라벨 폭 합 ≤ 1280 보장).
3. **가로 위젯 합산**: 같은 행에 들어가는 모든 위젯 → `contentsMargins.left + Σ(widget.minSizeHint() + spacing) + contentsMargins.right ≤ 1280` 을 종이/headless 로 계산. 긴 라벨(예: "Total Flow: 42.0 L/min" 23자) 추가 시 폰트 포인트 ↓ 또는 padding ↓ 로 보정.
4. **사용자 화면 확인**: smoke test (AST + 인스턴스화) 만으로 OK 처리 금지. `sudo systemctl restart cdu-local-ui.service` 후 **사용자에게 실제 화면 확인 요청**.

| 화면 영역 | 픽셀 | 고정 위젯 |
|---|---|---|
| Top bar | 1280 × 64 | `TopBarWidget.setFixedHeight(64)` ([main.py](../src/local_ui/main.py)) |
| Page area (Monitoring / History / Settings) | 1280 × 656 | `QStackedWidget` 자동 |
| Cooling Health SVG (Monitoring 내부) | 1280 × 580 ≈ | `CoolingHealthWidget` stretch=1 |
| Status strip (Monitoring 내부) | 1280 × 76 | `StatusStripWidget._STRIP_HEIGHT = 76` |

## Local UI (PySide6)

> Module structure and file-level descriptions: [`src/local_ui/STRUCTURE.md`](../src/local_ui/STRUCTURE.md)

**FE (PySide6)**
- 모니터링 페이지: 실시간 센서·제어·통신 상태 표시, Manual 모드에서 펌프·팬 PWM 제어, Mode 토글(Manual↔Auto)
- 기록 확인 페이지: Prometheus에서 센서 이력 및 Manual 제어 명령 이력 조회

**BE (PySide6)**
- MCG와 IPC 기반 통신 (PWM 제어 요청 전달)
- 모드 관리 (UI 독점): UI가 Redis `control:mode`의 쓰기 주체. MCG는 읽기만 함
  - 서비스 최초 기동 시 `control:mode` key가 비어있으면 `auto`로 SETNX (기본값 초기화)
  - Manual/Auto 토글: UI가 Redis `control:mode` 직접 SET (`manual` / `auto`) — MCG 경유 없음
- Redis Pub/Sub 구독 (`sensor:*`, `comm:*`, `control:mode` — 변경 시 즉시 수신)
  - `comm:status` 수신 → Top bar Link 상태 갱신
  - `control:mode` 수신 → Top bar Mode 토글 갱신
- Redis Keyspace Notifications 구독 (`alarm:*` SET/DEL 이벤트 — 알람 발생·해제 즉시 감지)
  - 활성 알람 유무/등급 → Top bar System 상태 갱신
- Prometheus DB 조회 (이력 데이터 소스)

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

Redis Key, Prometheus 메트릭 등 DB 상세는 [MCG.md §9](MCG.md#9-db-redis--prometheus) 참고.

- **Redis**: 현재값 전용. UI는 Pub/Sub(`sensor:*`, `comm:*`) + Keyspace Notifications(`alarm:*`)로 변경 즉시 수신.
- **Prometheus**: 이력 조회용 (History 페이지 데이터 소스).
