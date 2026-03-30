# 라즈베리파이 키오스크 모드 설계

## 개요

- **Target:** Raspberry Pi 4, Raspberry Pi OS Bookworm (64-bit)
- **Display Server:** X11 (Wayland 미사용 — PySide6 호환성 및 안정성 우선)
- **UI 모드:** Local UI (PySide6 앱) / WEB UI (Chromium 브라우저)
- **핵심 목표:** 부팅 후 자동으로 UI 진입, 비정상 종료 시 자동 재시작, HW 플랫폼 정보 비노출

---

## 1. 공통 설정

### 1.1 콘솔 자동 로그인

raspi-config 또는 systemd override로 `pi` 계정을 tty1에 자동 로그인 설정.

```bash
sudo raspi-config
# System Options → Boot / Auto Login → Console Autologin
```

또는 수동 설정:

```bash
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d/
sudo tee /etc/systemd/system/getty@tty1.service.d/autologin.conf << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin pi --noclear %I $TERM
EOF
sudo systemctl daemon-reload
```

### 1.2 화면 절전 및 전원 관리 비활성화

X11 세션 시작 시 `.xinitrc`에 아래 명령 추가 (섹션 2.2, 3.2 참고):

```bash
xset s off          # 화면 보호기 비활성화
xset -dpms          # DPMS(전원 절약) 비활성화
xset s noblank      # 화면 블랭킹 비활성화
```

### 1.3 마우스 커서 숨김

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
 └─ systemd getty auto-login (tty1)
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

# 화면 절전 비활성화
xset s off
xset -dpms
xset s noblank

# 마우스 커서 숨김
unclutter -idle 0 -root &

# PySide6 앱 실행 (비정상 종료 시 자동 재시작)
while true; do
    /home/pi/venv/bin/python /home/pi/l2a_cdu/ui/main.py
    sleep 2
done
```

> `while true` 루프로 앱 크래시 시 2초 후 자동 재시작.
> X 서버 종료는 루프 밖이므로 의도적 종료(SIGTERM 등)와 구분됨.

### 2.4 환경변수 설정

PySide6 앱이 올바른 디스플레이를 참조하도록 환경변수 설정:

```bash
# .xinitrc 상단에 추가
export DISPLAY=:0
export QT_QPA_PLATFORM=xcb        # X11 백엔드 명시
export QT_SCALE_FACTOR=1           # 해상도 스케일 고정
```

---

## 3. WEB UI (Chromium) 키오스크

### 3.1 구성 개요

```
부팅
 └─ systemd getty auto-login (tty1)
     └─ .bash_profile → startx
         └─ .xinitrc
             ├─ 환경 설정 (xset, unclutter)
             ├─ openbox (최소 WM) &
             └─ 재시작 루프: Chromium 키오스크 모드 실행
```

FastAPI 백엔드 및 Svelte 정적 파일 서버는 systemd 서비스로 선행 기동 (섹션 4.2 참고).

### 3.2 .xinitrc 설정

```bash
# ~/.xinitrc (WEB UI 모드)

# 화면 절전 비활성화
xset s off
xset -dpms
xset s noblank

# 마우스 커서 숨김
unclutter -idle 0 -root &

# 최소 윈도우 매니저 (chromium 전체화면 유지용)
openbox &

# Chromium 첫 실행 시 프로파일 오류 방지
mkdir -p /home/pi/.config/chromium-kiosk

# Chromium 키오스크 모드 실행 (비정상 종료 시 자동 재시작)
while true; do
    chromium-browser \
        --kiosk \
        --noerrdialogs \
        --disable-infobars \
        --disable-session-crashed-bubble \
        --disable-restore-session-state \
        --no-first-run \
        --user-data-dir=/home/pi/.config/chromium-kiosk \
        http://localhost:3000
    sleep 2
done
```

### 3.3 openbox 설치

```bash
sudo apt install openbox
```

---

## 4. 서비스 관리 (systemd)

PCG 및 FastAPI 백엔드는 X11 세션과 독립적으로 systemd 서비스로 관리.
UI 기동 전에 반드시 실행되어야 하므로 `multi-user.target` 단계에서 시작.

### 4.1 PCG 서비스

```ini
# /etc/systemd/system/pcg.service
[Unit]
Description=L2A CDU Python Control Gateway
After=network.target redis.service
Wants=redis.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/l2a_cdu/pcg
ExecStart=/home/pi/venv/bin/python main.py
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
User=pi
WorkingDirectory=/home/pi/l2a_cdu/web
ExecStart=/home/pi/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 4.3 서비스 등록

```bash
sudo systemctl daemon-reload
sudo systemctl enable pcg.service
sudo systemctl enable fastapi.service   # WEB UI 사용 시
sudo systemctl start pcg.service
```

---

## 5. 부팅 시퀀스

```
[전원 ON]
    │
    ▼
[systemd: multi-user.target]
    ├─ redis.service 시작
    ├─ pcg.service 시작
    └─ fastapi.service 시작 (WEB UI 사용 시)
    │
    ▼
[getty@tty1: auto-login → pi]
    │
    ▼
[.bash_profile → startx]
    │
    ▼
[.xinitrc]
    ├─ xset / unclutter 환경 설정
    └─ UI 실행 루프
         ├─ (Local) PySide6 앱 ← IPC → PCG
         └─ (WEB)   Chromium → localhost:3000 ← REST → FastAPI ← IPC → PCG
```

---

## 6. 요약

| 항목 | Local UI (PySide6) | WEB UI (Chromium) |
|---|---|---|
| X 서버 기동 | startx (.bash_profile) | startx (.bash_profile) |
| 윈도우 매니저 | 불필요 | openbox (최소) |
| UI 실행 | PySide6 앱 (.xinitrc while loop) | Chromium --kiosk (.xinitrc while loop) |
| 백엔드 서비스 | PCG (systemd) | PCG + FastAPI (systemd) |
| 재시작 방식 | .xinitrc while loop | .xinitrc while loop |
| 화면 절전 비활성화 | xset (.xinitrc) | xset (.xinitrc) |
| 커서 숨김 | unclutter + -nocursor | unclutter + -nocursor |
