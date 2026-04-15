#!/usr/bin/env bash
# install.sh — Deploy CDU system services to /etc/systemd/system/
#
# Usage:
#   sudo bash scripts/install.sh          # install + enable services
#   sudo bash scripts/install.sh status   # show service status
#   sudo bash scripts/install.sh stop     # stop all CDU services
#   sudo bash scripts/install.sh remove   # disable + remove service files

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVICES_SRC="$PROJECT_ROOT/scripts/services"
SERVICES_DST="/etc/systemd/system"
CONFIG_FILE="$PROJECT_ROOT/config/config.yaml"
VENV_PYTHON="/home/gadgetini/venv/bin/python"
XINITRC="/home/gadgetini/.xinitrc"
BASH_PROFILE="/home/gadgetini/.bash_profile"
USER="gadgetini"

# ── Helpers ──────────────────────────────────────────────────────────────────

log()  { echo "[install] $*"; }
warn() { echo "[install] WARN: $*" >&2; }
die()  { echo "[install] ERROR: $*" >&2; exit 1; }

require_root() {
    [ "$EUID" -eq 0 ] || die "Run with sudo: sudo bash $0"
}

read_mode() {
    if command -v python3 &>/dev/null && [ -f "$CONFIG_FILE" ]; then
        python3 -c "
import yaml, sys
with open('$CONFIG_FILE') as f:
    d = yaml.safe_load(f)
print(d.get('mode', 'fake'))
" 2>/dev/null || echo "fake"
    else
        grep -E '^mode:' "$CONFIG_FILE" | awk '{print $2}' | tr -d "'\"" || echo "fake"
    fi
}

# ── Install ───────────────────────────────────────────────────────────────────

do_install() {
    require_root

    # System dependencies required by PySide6 xcb platform plugin (Qt 6.5+)
    log "Installing system dependencies..."
    apt-get install -y --no-install-recommends \
        libxcb-cursor0 \
        unclutter \
        fonts-noto-color-emoji \
        2>/dev/null || warn "apt-get failed — install packages manually if needed"

    MODE=$(read_mode)
    log "Config mode: $MODE"

    # Always install pushgateway service
    install_service "pushgateway.service"

    # Mode-specific services
    if [ "$MODE" = "fake" ]; then
        install_service "cdu-fake-simulator.service"
        log "Fake simulator service installed."
    else
        log "Real mode: skipping fake simulator service."
        # MCG service will be added here when implemented
    fi

    systemctl daemon-reload
    log "systemd daemon reloaded."

    # Enable + start installed services
    enable_service "pushgateway.service"

    if [ "$MODE" = "fake" ]; then
        enable_service "cdu-fake-simulator.service"
    fi

    # Kiosk setup
    setup_bash_profile
    setup_xinitrc

    log ""
    log "Installation complete."
    log "Reboot or run: sudo systemctl start cdu-fake-simulator (fake mode)"
}

install_service() {
    local name="$1"
    local src="$SERVICES_SRC/$name"
    local dst="$SERVICES_DST/$name"

    [ -f "$src" ] || die "Service file not found: $src"
    cp "$src" "$dst"
    log "Copied $name → $SERVICES_DST/"
}

enable_service() {
    local name="$1"
    systemctl enable "$name"
    log "Enabled $name"
}

# ── Kiosk setup ───────────────────────────────────────────────────────────────

setup_bash_profile() {
    if [ -f "$BASH_PROFILE" ]; then
        log ".bash_profile already exists — skipping."
        return
    fi

    cat > "$BASH_PROFILE" << 'EOF'
# Auto-start X server on tty1 login
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    startx -- -nocursor 2>/dev/null
fi
EOF
    chown "$USER:$USER" "$BASH_PROFILE"
    log ".bash_profile created."
}

setup_xinitrc() {
    cat > "$XINITRC" << EOF
#!/bin/bash
# ~/.xinitrc — CDU kiosk session

export DISPLAY=:0
export QT_QPA_PLATFORM=xcb
export QT_SCALE_FACTOR=1

# Disable screen saver / power management
xset s off
xset -dpms
xset s noblank

# Hide mouse cursor (requires: sudo apt install unclutter)
# unclutter -idle 0 -root &

# Run PySide6 UI with auto-restart on crash
while true; do
    $VENV_PYTHON $PROJECT_ROOT/src/local_ui/main.py
    sleep 2
done
EOF
    chown "$USER:$USER" "$XINITRC"
    chmod +x "$XINITRC"
    log ".xinitrc updated → $PROJECT_ROOT/src/local_ui/main.py"
}

# ── Status ────────────────────────────────────────────────────────────────────

do_status() {
    for svc in pushgateway.service cdu-fake-simulator.service; do
        echo "─── $svc ───────────────────────────"
        systemctl status "$svc" --no-pager -l 2>/dev/null || echo "  (not installed)"
    done
}

# ── Stop ──────────────────────────────────────────────────────────────────────

do_stop() {
    require_root
    for svc in cdu-fake-simulator.service; do
        systemctl stop "$svc" 2>/dev/null && log "Stopped $svc" || warn "$svc not running"
    done
}

# ── Remove ────────────────────────────────────────────────────────────────────

do_remove() {
    require_root
    for svc in cdu-fake-simulator.service pushgateway.service; do
        systemctl stop    "$svc" 2>/dev/null || true
        systemctl disable "$svc" 2>/dev/null || true
        rm -f "$SERVICES_DST/$svc"
        log "Removed $svc"
    done
    systemctl daemon-reload
    log "Removal complete."
}

# ── Entry point ───────────────────────────────────────────────────────────────

CMD="${1:-install}"
case "$CMD" in
    install) do_install ;;
    status)  do_status  ;;
    stop)    do_stop    ;;
    remove)  do_remove  ;;
    *) die "Unknown command '$CMD'. Use: install | status | stop | remove" ;;
esac
