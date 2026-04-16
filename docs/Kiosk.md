# 라즈베리파이 키오스크 모드 설계

---

## 진행 상황 (최종 확인: 2026-04-16)

| 항목 | 섹션 | 상태 | 비고 |
|---|---|---|---|
| LightDM 비활성화 | 1.1 | ✅ 완료 | disabled |
| getty@tty1 mask | 1.2 | ✅ 완료 | UI 서비스가 직접 vt1 점유 — 콘솔 로그인 단계 제거 |
| Xwrapper 설정 | 1.3 | ✅ 완료 | `allowed_users=anybody`, `needs_root_rights=no` (systemd가 X 기동 가능) |
| 화면 절전 비활성화 | 1.4 | ✅ 완료 | 세션 스크립트에서 xset 처리 |
| unclutter 설치 | 1.5 | ⏳ 미완 | `sudo apt install unclutter` 필요 |
| Plymouth 테마 l2a-cdu 설치 | 2.3 | ✅ 완료 | |
| Plymouth → X 무전환 검정 화면 제거 | 2.4 | ✅ 완료 | `plymouth-quit.service` drop-in으로 `--retain-splash` 적용 |
| cmdline.txt 설정 (quiet splash) | 2.5 | ✅ 완료 | console=tty1 제거 확인 |
| **Python venv 생성** | — | ✅ 완료 | `/home/gadgetini/venv` (Python 3.11) |
| **UI 프레임워크 설치 (PySide6)** | — | ✅ 완료 | PySide6 6.8.0.2 |
| **백엔드 패키지 설치** | — | ✅ 완료 | redis 7.4.0, pymodbus 3.12.1, fastapi 0.135.3, uvicorn 0.42.0, prometheus-client 0.24.1, httpx 0.28.1, requests 2.33.1 |
| redis-server 서비스 | 3.4 | ✅ 완료 | enabled |
| prometheus 서비스 | 3.4 | ✅ 완료 | enabled |
| pushgateway 서비스 | 3.4 | ✅ 완료 | |
| cdu-fake-simulator 서비스 | — | ✅ 완료 | fake 모드 전용 |
| **cdu-local-ui 서비스 (X+UI 직접 기동)** | 3.1 | ✅ 완료 | xinit으로 X 서버 + 세션 스크립트 동시 실행 |
| MCG 서비스 | 3.2 | ❌ 미완 | 서비스 파일 없음 (real 모드 구현 시 추가 예정) |
| FastAPI 서비스 | 3.3 | ❌ 미완 | 서비스 파일 없음 |

**남은 작업 순서:**
1. `sudo apt install unclutter` (1.5)
2. `/etc/systemd/system/mcg.service` 생성 + enable (3.2) — real 모드 구현 시
3. `/etc/systemd/system/fastapi.service` 생성 + enable (3.3) — WEB UI 사용 시
4. `scripts/install.sh` 갱신 — 새 키오스크 구조(getty mask, Xwrapper, plymouth drop-in)에 맞춰 자동화 명령 업데이트

---

## 개요

- **Target:** Raspberry Pi 4, Raspberry Pi OS Bookworm (64-bit)
- **User:** `gadgetini`
- **Display Server:** X11 (Wayland 미사용 — PySide6 호환성 및 안정성 우선)
- **UI 모드:** Local UI (PySide6 앱) — 터치 디스플레이 키오스크 전용
- **핵심 목표:** 부팅 후 **콘솔/터미널 노출 없이** UI 서비스가 직접 X 서버와 PySide6를 기동, 비정상 종료 시 자동 재시작, HW 플랫폼 정보 비노출

**구조 핵심**: getty/bash/startx 체인을 사용하지 않고, `cdu-local-ui.service`가 `xinit`으로 X 서버와 세션 스크립트를 직접 실행. Plymouth → X 사이의 검정 화면도 `--retain-splash`로 제거.

---

## 1. 공통 설정

### 1.1 LightDM 비활성화

```bash
sudo systemctl disable lightdm.service
sudo systemctl stop lightdm.service
```

### 1.2 getty@tty1 mask

UI 서비스가 vt1을 직접 점유하므로 콘솔 자동 로그인은 사용하지 않음. tty2~6은 그대로 남겨 관리자 콘솔 접근(Ctrl+Alt+F2) 가능.

```bash
sudo systemctl mask getty@tty1.service
```

### 1.3 Xwrapper 설정

systemd 서비스(비-console 세션)가 X 서버를 기동할 수 있도록 허용.

```bash
sudo tee /etc/X11/Xwrapper.config << 'EOF'
allowed_users=anybody
needs_root_rights=no
EOF
```

> `gadgetini`는 이미 `video`, `input`, `tty`, `render` 그룹에 속해 있어 DRM/입력 접근 권한 보유.

### 1.4 화면 절전·전원 관리 비활성화

세션 스크립트(`scripts/cdu_session.sh`)에서 `xset` 명령으로 처리. 별도 시스템 설정 불필요.

```bash
xset s off          # 화면 보호기 비활성화
xset -dpms          # DPMS(전원 절약) 비활성화
xset s noblank      # 화면 블랭킹 비활성화
```

### 1.5 마우스 커서 숨김

```bash
sudo apt install unclutter
```

세션 스크립트에서 `unclutter -idle 0 -root &` 실행. 또한 `xinit` 호출 시 `-- :0 vt1 -nocursor` 인자로 X 서버 레벨에서도 기본 커서 숨김.

---

## 2. Plymouth 부트 스플래시

### 2.1 개요

OS 부팅 시작(커널 로딩)부터 systemd 서비스 기동 완료까지 전 구간에 커스텀 로고를 표시.
라즈베리파이 기본 로고 및 부팅 텍스트를 완전히 숨겨 HW 플랫폼 정보를 비노출.

```
[전원 ON] → [커널] → [Plymouth 스플래시: L2A 로고] → [systemd 서비스 기동] → [PySide6 앱]
```

### 2.2 설치

```bash
sudo apt install plymouth plymouth-themes
```

### 2.3 커스텀 테마 생성

테마 디렉토리 생성:

```bash
sudo mkdir -p /usr/share/plymouth/themes/l2a-cdu
```

로고 이미지 배치:

```bash
sudo cp /home/gadgetini/L2A_CDU_system/assets/logo.png /usr/share/plymouth/themes/l2a-cdu/logo.png
```

> 로고 변경 시 아래 명령으로 재배치 후 initramfs를 다시 빌드해야 적용됨:
> ```bash
> sudo cp /home/gadgetini/L2A_CDU_system/assets/logo.png /usr/share/plymouth/themes/l2a-cdu/logo.png
> sudo plymouth-set-default-theme l2a-cdu -R
> ```

> **이미지 스펙**
> - 디스플레이: Raspberry Pi Touch Display 2, 1280 × 720 (landscape, ~210 PPI)
> - 권장 로고 크기: **640 × 360 px** (화면의 50%)
> - 포맷: PNG, 배경 투명 권장
> - 배치·배경색은 스크립트가 자동 처리 (중앙 배치, 배경 검정)

테마 정의 파일 생성:

```bash
sudo tee /usr/share/plymouth/themes/l2a-cdu/l2a-cdu.plymouth << 'EOF'
[Plymouth Theme]
Name=L2A CDU
Description=L2A CDU Boot Splash
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/l2a-cdu
ScriptFile=/usr/share/plymouth/themes/l2a-cdu/l2a-cdu.script
EOF
```

스크립트 파일 생성 (로고 중앙 배치, 배경 검정):

```bash
sudo tee /usr/share/plymouth/themes/l2a-cdu/l2a-cdu.script << 'EOF'
wallpaper_image = Image("logo.png");
screen_width = Window.GetWidth();
screen_height = Window.GetHeight();
img_width = wallpaper_image.GetWidth();
img_height = wallpaper_image.GetHeight();

x = (screen_width - img_width) / 2;
y = (screen_height - img_height) / 2;

sprite = Sprite(wallpaper_image);
sprite.SetX(x);
sprite.SetY(y);
sprite.SetZ(10);

Window.SetBackgroundTopColor(0, 0, 0);
Window.SetBackgroundBottomColor(0, 0, 0);
EOF
```

### 2.4 테마 적용 및 initramfs 업데이트

```bash
sudo plymouth-set-default-theme l2a-cdu -R
```

> `-R` 옵션이 `update-initramfs -u`를 자동 실행함.

### 2.5 cmdline.txt 설정

부팅 텍스트 숨김 및 스플래시 활성화:

```bash
# /boot/firmware/cmdline.txt 편집
# 기존 항목에서 console=tty1 제거, 아래 항목 추가
sudo sed -i 's/console=tty1 //' /boot/firmware/cmdline.txt
sudo sed -i 's/$/ quiet splash plymouth.ignore-serial-consoles/' /boot/firmware/cmdline.txt
```

> `quiet`: 커널 부팅 메시지 숨김
> `splash`: Plymouth 스플래시 활성화
> `console=tty1` 제거: 부팅 텍스트가 화면에 출력되지 않도록 함

### 2.6 적용 확인

```bash
# 현재 적용된 테마 확인
plymouth-set-default-theme --list
sudo plymouth-set-default-theme  # 현재 기본 테마 출력
```

### 2.7 Plymouth → X 전환 시 검정 화면 제거 (`--retain-splash`)

기본 `plymouth-quit.service`는 `multi-user.target` 도달 시 즉시 Plymouth를 종료한다. 그 직후 `cdu-local-ui.service`가 X 서버를 띄우는 ~1초 동안 검정 화면이 보인다. 아래 drop-in으로 종료 시 `--retain-splash`를 사용하면 X가 첫 프레임을 그릴 때까지 스플래시 이미지가 프레임버퍼에 남아 검정 화면이 사라진다.

```bash
sudo mkdir -p /etc/systemd/system/plymouth-quit.service.d
sudo tee /etc/systemd/system/plymouth-quit.service.d/retain-splash.conf << 'EOF'
[Service]
ExecStart=
ExecStart=-/usr/bin/plymouth quit --retain-splash
EOF
sudo systemctl daemon-reload
```

---

## 3. 서비스 관리 (systemd)

`multi-user.target` 단계에서 모든 백엔드 서비스 기동. UI 서비스(`cdu-local-ui`)가 X 서버까지 직접 책임지므로 별도 디스플레이 매니저나 getty 로그인 단계 없음.

| 서비스 | 관리 방식 | 비고 |
|---|---|---|
| Redis | apt 패키지 — systemd 자동 등록 | `redis-server` |
| Prometheus | apt 패키지 — systemd 자동 등록 | `prometheus` |
| Pushgateway | 수동 설치 — systemd 등록 필요 | 바이너리: `/home/gadgetini/pushgateway/pushgateway` |
| **cdu-local-ui** | 레포 → 배포 (섹션 3.1) | **xinit으로 X 서버 + PySide6 동시 기동** |
| cdu-fake-simulator | 레포 → 배포 | fake 모드 전용 시뮬레이터 |
| MCG | 수동 등록 (섹션 3.2) | real 모드 구현 시 |
| FastAPI | 수동 등록 (섹션 3.3) | 원격 WEB UI 접속용 |

### 3.1 cdu-local-ui 서비스 (X 서버 + UI 동시 기동)

```ini
# /etc/systemd/system/cdu-local-ui.service
[Unit]
Description=L2A CDU Local UI (X server + PySide6 kiosk)
After=multi-user.target redis.service systemd-user-sessions.service
Wants=redis.service
Conflicts=getty@tty1.service

[Service]
Type=simple
User=gadgetini
PAMName=login
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes
TTYVTDisallocate=yes
StandardInput=tty
StandardOutput=journal
StandardError=journal
WorkingDirectory=/home/gadgetini/L2A_CDU_system

Environment=DISPLAY=:0
Environment=XDG_RUNTIME_DIR=/run/user/1000
Environment=QT_QPA_PLATFORM=xcb
Environment=QT_SCALE_FACTOR=1

ExecStart=/usr/bin/xinit /home/gadgetini/L2A_CDU_system/scripts/cdu_session.sh -- :0 vt1 -nocursor -nolisten tcp
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

**세션 스크립트** (`scripts/cdu_session.sh`): `xinit`이 X 서버 기동 후 호출하는 사용자 세션 스크립트. X 환경 설정(xset/unclutter) 후 PySide6 앱을 `while true` 루프로 실행하여 **앱 크래시는 앱만 재시작, X 서버는 유지**. `xinit` 자체가 죽으면 systemd가 서비스 전체를 재시작.

```bash
#!/bin/bash
# scripts/cdu_session.sh
set -u

VENV_PYTHON="/home/gadgetini/venv/bin/python"
APP_MAIN="/home/gadgetini/L2A_CDU_system/src/local_ui/main.py"

xset s off
xset -dpms
xset s noblank
unclutter -idle 0 -root &

while true; do
    "$VENV_PYTHON" "$APP_MAIN"
    sleep 2
done
```

> `xinit ... -- :0 vt1 -nocursor`: X 서버를 vt1 위에 띄우고 기본 마우스 커서 숨김. `-nolisten tcp`는 외부 X 클라이언트 접속 차단(보안).
> `PAMName=login`: logind가 `XDG_RUNTIME_DIR`(`/run/user/1000`) 등을 자동 생성하도록 PAM 세션 활성화.

### 3.2 MCG 서비스

```ini
# /etc/systemd/system/mcg.service
[Unit]
Description=L2A CDU Modbus Control Gateway
After=network.target redis.service
Wants=redis.service

[Service]
Type=simple
User=gadgetini
WorkingDirectory=/home/gadgetini/L2A_CDU_system/pcg
ExecStart=/home/gadgetini/venv/bin/python main.py
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 3.3 FastAPI 서비스 (WEB UI 사용 시)

```ini
# /etc/systemd/system/fastapi.service
[Unit]
Description=L2A CDU FastAPI Backend
After=network.target redis.service mcg.service
Wants=redis.service

[Service]
Type=simple
User=gadgetini
WorkingDirectory=/home/gadgetini/L2A_CDU_system/web
ExecStart=/home/gadgetini/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 3.4 Prometheus 서비스

apt 설치 시 자동 등록됨. 설정 파일 경로:

```
/etc/prometheus/prometheus.yml
/var/lib/prometheus/           ← 데이터 저장 경로
```

활성화만 확인:

```bash
sudo systemctl enable prometheus
sudo systemctl start prometheus
```

### 3.5 Pushgateway 서비스

수동 설치 후 아래 서비스 파일 등록:

```ini
# /etc/systemd/system/pushgateway.service
[Unit]
Description=Prometheus Pushgateway
After=network.target

[Service]
Type=simple
User=gadgetini
ExecStart=/home/gadgetini/pushgateway/pushgateway
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### 3.6 서비스 등록

```bash
# Redis (apt 설치 시 자동 등록 — 활성화만)
sudo systemctl enable redis-server

# Prometheus (apt 설치 시 자동 등록 — 활성화만)
sudo systemctl enable prometheus

# Pushgateway
sudo systemctl daemon-reload
sudo systemctl enable pushgateway.service

# UI (X 서버 + PySide6 직접 기동)
sudo systemctl enable cdu-local-ui.service

# MCG / FastAPI
sudo systemctl enable mcg.service
sudo systemctl enable fastapi.service   # WEB UI 사용 시
```

---

## 4. 부팅 시퀀스

```
[전원 ON]
    │
    ▼
[커널 로딩 + Plymouth 스플래시: L2A 로고]
    │
    ▼
[systemd: multi-user.target]
    ├─ redis-server.service
    ├─ prometheus.service
    ├─ pushgateway.service
    ├─ cdu-fake-simulator.service (fake 모드) 또는 mcg.service (real 모드)
    ├─ fastapi.service (원격 WEB UI 접속용)
    └─ plymouth-quit.service → plymouth quit --retain-splash
                              (스플래시 이미지가 프레임버퍼에 잔류)
    │
    ▼
[cdu-local-ui.service]
    └─ /usr/bin/xinit scripts/cdu_session.sh -- :0 vt1 -nocursor
        ├─ Xorg 서버 기동 → vt1 점유 → 스플래시 화면을 X 화면으로 자연 전환
        └─ cdu_session.sh
            ├─ xset / unclutter 환경 설정
            └─ PySide6 앱 재시작 루프 ← IPC → MCG
```

> getty@tty1는 mask되어 부팅 과정에서 콘솔/터미널이 화면에 노출되지 않음. tty2~6은 살아있어 Ctrl+Alt+F2로 관리자 콘솔 접근 가능.

---

## 5. 요약

| 항목 | 내용 |
|---|---|
| X 서버 기동 | `cdu-local-ui.service` 내부의 `xinit` (systemd 직접 실행) |
| 콘솔/터미널 단계 | 없음 (`getty@tty1` mask) |
| 윈도우 매니저 | 불필요 |
| UI 실행 | `scripts/cdu_session.sh`의 PySide6 while 루프 (`xinit`이 실행) |
| 앱 재시작 | 세션 스크립트 while 루프 (X 서버 유지, 앱만 2초 후 재시작) |
| 서비스 재시작 | systemd `Restart=always` (X 서버 자체가 죽은 경우만) |
| 백엔드 서비스 | Redis, Prometheus, Pushgateway, cdu-fake-simulator(또는 MCG), FastAPI |
| 화면 절전 비활성화 | xset (세션 스크립트) |
| 커서 숨김 | unclutter (세션 스크립트) + `xinit -nocursor` |
| 부트 스플래시 | Plymouth (l2a-cdu 테마, 로고 중앙 배치, 배경 검정) |
| Plymouth → X 전환 | `plymouth-quit.service` drop-in으로 `--retain-splash` 적용 (검정 화면 없음) |
| 관리자 콘솔 접근 | tty2~6 살아있음 (Ctrl+Alt+F2), SSH (Top bar에 IP 표시) |
