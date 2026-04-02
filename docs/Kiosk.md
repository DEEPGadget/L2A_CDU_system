# 라즈베리파이 키오스크 모드 설계

---

## 진행 상황 (최종 확인: 2026-04-02)

| 항목 | 섹션 | 상태 | 비고 |
|---|---|---|---|
| LightDM 비활성화 | 1.1 | ✅ 완료 | |
| 콘솔 자동 로그인 (autologin.conf) | 1.2 | ✅ 완료 | |
| 화면 절전 비활성화 (xset) | 1.3 | ✅ 완료 | .xinitrc에 포함 |
| unclutter 설치 | 1.4 | ❌ 미완 | apt install 필요. 설치 후 .xinitrc 주석 해제 |
| .bash_profile (startx 자동 실행) | 2.2 | ❌ 미완 | 파일 없음 |
| .xinitrc (앱 재시작 루프) | 2.3 | ✅ 완료 | unclutter 줄만 주석 처리 — 설치 후 해제 필요 |
| Plymouth 테마 l2a-cdu 설치 | 3.3 | ✅ 완료 | logo.png, script, theme 파일 모두 존재 |
| Plymouth 테마 적용 (initramfs) | 3.4 | ✅ 완료 | |
| cmdline.txt 설정 (quiet splash) | 3.5 | ✅ 완료 | console=tty1 제거 확인 |
| **Python venv 생성** | — | ✅ 완료 | `/home/gadgetini/venv` (Python 3.11) |
| **UI 프레임워크 설치 (PySide6)** | — | ✅ 완료 | PySide6 6.8.0.2 |
| **백엔드 패키지 설치** | — | ✅ 완료 | redis 7.4.0, pymodbus 3.12.1, fastapi 0.135.3, uvicorn 0.42.0, prometheus-client 0.24.1, httpx 0.28.1, requests 2.33.1 |
| redis-server 서비스 | 4.3/4.5 | ✅ 완료 | enabled |
| prometheus 서비스 | 4.3/4.5 | ✅ 완료 | enabled |
| pushgateway 서비스 | 4.4/4.5 | ❌ 미완 | 서비스 파일 없음 |
| PCG 서비스 | 4.1/4.5 | ❌ 미완 | 서비스 파일 없음 |
| FastAPI 서비스 | 4.2/4.5 | ❌ 미완 | 서비스 파일 없음 |

**남은 작업 순서:**
1. `sudo systemctl disable lightdm` (1.1)
2. `sudo apt install unclutter` (1.4)
3. `~/.bash_profile` 생성 (2.2)
4. `~/.xinitrc` 생성 (2.3)
5. `/etc/systemd/system/pcg.service` 생성 + enable (4.1)
6. `/etc/systemd/system/fastapi.service` 생성 + enable (4.2) — WEB UI 사용 시
7. `/etc/systemd/system/pushgateway.service` 생성 + enable (4.4) — pushgateway 바이너리 있을 경우

---

## 개요

- **Target:** Raspberry Pi 4, Raspberry Pi OS Bookworm (64-bit)
- **User:** `gadgetini`
- **Display Server:** X11 (Wayland 미사용 — PySide6 호환성 및 안정성 우선)
- **UI 모드:** Local UI (PySide6 앱) — 터치 디스플레이 키오스크 전용
- **핵심 목표:** 부팅 후 자동으로 UI 진입, 비정상 종료 시 자동 재시작, HW 플랫폼 정보 비노출

---

## 1. 공통 설정

### 1.1 LightDM 비활성화

기존 디스플레이 매니저(LightDM)를 비활성화하고 콘솔 자동 로그인으로 전환.

```bash
sudo systemctl disable lightdm.service
sudo systemctl stop lightdm.service
```

### 1.2 콘솔 자동 로그인

```bash
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d/
sudo tee /etc/systemd/system/getty@tty1.service.d/autologin.conf << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin gadgetini --noclear %I $TERM
EOF
sudo systemctl daemon-reload
```

### 1.3 화면 절전 및 전원 관리 비활성화

X11 세션 시작 시 `.xinitrc`에 아래 명령 추가 (섹션 2.3 참고):

```bash
xset s off          # 화면 보호기 비활성화
xset -dpms          # DPMS(전원 절약) 비활성화
xset s noblank      # 화면 블랭킹 비활성화
```

### 1.4 마우스 커서 숨김

`unclutter` 설치 후 X11 세션 시작 시 실행:

```bash
sudo apt install unclutter
```

`.xinitrc`에 추가:

```bash
unclutter -idle 0 -root &
```

---

## 2. Local UI (PySide6) 키오스크

### 2.1 구성 개요

```
부팅
 └─ systemd getty auto-login (tty1, gadgetini)
     └─ .bash_profile → startx
         └─ .xinitrc
             ├─ 환경 설정 (xset, unclutter)
             └─ 재시작 루프: PySide6 앱 실행
```

PCG는 UI와 별개로 systemd 서비스로 먼저 기동 (섹션 4.1 참고).

### 2.2 .bash_profile 설정

tty1에 로그인 시 자동으로 X 서버 시작:

```bash
# ~/.bash_profile
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    startx -- -nocursor 2>/dev/null
fi
```

> `-- -nocursor`: X 서버 레벨에서 기본 커서 숨김

### 2.3 .xinitrc 설정

```bash
# ~/.xinitrc

# 환경변수
export DISPLAY=:0
export QT_QPA_PLATFORM=xcb        # X11 백엔드 명시
export QT_SCALE_FACTOR=1           # 해상도 스케일 고정

# 화면 절전 비활성화
xset s off
xset -dpms
xset s noblank

# 마우스 커서 숨김
unclutter -idle 0 -root &

# PySide6 앱 실행 (비정상 종료 시 자동 재시작)
while true; do
    /home/gadgetini/venv/bin/python /home/gadgetini/L2A_CDU_system/ui/main.py
    sleep 2
done
```

> `while true` 루프로 앱 크래시 시 2초 후 자동 재시작.
> X 서버 종료는 루프 밖이므로 의도적 종료(SIGTERM 등)와 구분됨.

---

## 3. Plymouth 부트 스플래시

### 3.1 개요

OS 부팅 시작(커널 로딩)부터 systemd 서비스 기동 완료까지 전 구간에 커스텀 로고를 표시.
라즈베리파이 기본 로고 및 부팅 텍스트를 완전히 숨겨 HW 플랫폼 정보를 비노출.

```
[전원 ON] → [커널] → [Plymouth 스플래시: L2A 로고] → [systemd 서비스 기동] → [PySide6 앱]
```

### 3.2 설치

```bash
sudo apt install plymouth plymouth-themes
```

### 3.3 커스텀 테마 생성

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

### 3.4 테마 적용 및 initramfs 업데이트

```bash
sudo plymouth-set-default-theme l2a-cdu -R
```

> `-R` 옵션이 `update-initramfs -u`를 자동 실행함.

### 3.5 cmdline.txt 설정

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

### 3.6 적용 확인

```bash
# 현재 적용된 테마 확인
plymouth-set-default-theme --list
sudo plymouth-set-default-theme  # 현재 기본 테마 출력
```

---

## 4. 서비스 관리 (systemd)

아래 서비스들은 X11 세션과 독립적으로 `multi-user.target` 단계에서 기동.
Local UI 키오스크 진입 전 모두 실행되어야 함. FastAPI는 원격 WEB UI 접속을 위해 상시 실행.

| 서비스 | 관리 방식 | 비고 |
|---|---|---|
| Redis | apt 패키지 — systemd 자동 등록 | `redis-server` |
| Prometheus | apt 패키지 — systemd 자동 등록 | `prometheus` |
| Pushgateway | 수동 설치 — systemd 등록 필요 | 바이너리: `/home/gadgetini/pushgateway/pushgateway` |
| PCG | 수동 등록 (섹션 4.1) | |
| FastAPI | 수동 등록 (섹션 4.2) | 원격 WEB UI 접속용 |

### 4.1 PCG 서비스

```ini
# /etc/systemd/system/pcg.service
[Unit]
Description=L2A CDU Python Control Gateway
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

### 4.2 FastAPI 서비스 (WEB UI 사용 시)

```ini
# /etc/systemd/system/fastapi.service
[Unit]
Description=L2A CDU FastAPI Backend
After=network.target redis.service pcg.service
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

### 4.3 Prometheus 서비스

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

### 4.4 Pushgateway 서비스

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

### 4.5 서비스 등록

```bash
# Redis (apt 설치 시 자동 등록 — 활성화만)
sudo systemctl enable redis-server

# Prometheus (apt 설치 시 자동 등록 — 활성화만)
sudo systemctl enable prometheus

# Pushgateway
sudo systemctl daemon-reload
sudo systemctl enable pushgateway.service

# PCG / FastAPI
sudo systemctl enable pcg.service
sudo systemctl enable fastapi.service   # WEB UI 사용 시
```

---

## 5. 부팅 시퀀스

```
[전원 ON]
    │
    ▼
[커널 로딩 + Plymouth 스플래시 시작: L2A 로고 표시]
    │
    ▼
[systemd: multi-user.target]
    ├─ redis-server.service 시작
    ├─ prometheus.service 시작
    ├─ pushgateway.service 시작
    ├─ pcg.service 시작
    └─ fastapi.service 시작 (원격 WEB UI 접속용)
    │
    ▼
[Plymouth 스플래시 종료]
    │
    ▼
[getty@tty1: auto-login → gadgetini]
    │
    ▼
[.bash_profile → startx]
    │
    ▼
[.xinitrc]
    ├─ xset / unclutter 환경 설정
    └─ PySide6 앱 재시작 루프 ← IPC → PCG
```

---

## 6. 요약

| 항목 | 내용 |
|---|---|
| X 서버 기동 | startx (.bash_profile) |
| 윈도우 매니저 | 불필요 |
| UI 실행 | PySide6 앱 (.xinitrc while loop) |
| 백엔드 서비스 | PCG, FastAPI, Redis, Prometheus, Pushgateway (systemd) |
| 재시작 방식 | .xinitrc while loop (크래시 시 2초 후 재시작) |
| 화면 절전 비활성화 | xset (.xinitrc) |
| 커서 숨김 | unclutter + -nocursor |
| 부트 스플래시 | Plymouth (script 모듈, 로고 중앙 배치, 배경 검정) |
