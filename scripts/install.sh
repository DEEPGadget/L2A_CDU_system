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
USER="gadgetini"

# ── Helpers ──────────────────────────────────────────────────────────────────

log()  { echo "[install] $*"; }
warn() { echo "[install] WARN: $*" >&2; }
die()  { echo "[install] ERROR: $*" >&2; exit 1; }

require_root() {
    [ "$EUID" -eq 0 ] || die "Run with sudo: sudo bash $0"
}

read_mode() {
    # Simple grep (PyYAML may not be installed for sudo's system python3).
    # config.yaml top-level `mode:` is always a single token, no quoting.
    if [ -f "$CONFIG_FILE" ]; then
        local m
        m=$(grep -E '^mode:' "$CONFIG_FILE" | awk '{print $2}' | tr -d "'\"")
        echo "${m:-fake}"
    else
        echo "fake"
    fi
}

# ── Install ───────────────────────────────────────────────────────────────────

do_install() {
    require_root

    # System dependencies:
    #   - libxcb-cursor0 : PySide6 xcb platform plugin (Qt 6.5+)
    #   - xserver-xorg / xinit / x11-xserver-utils : kiosk X session
    #     (cdu_session.sh uses xinit, xset, xsetroot)
    #   - unclutter : hide mouse cursor in kiosk
    #   - fonts-noto-color-emoji : UI glyphs
    #   - nodejs / npm : build the SvelteKit web frontend
    #   - nginx : reverse proxy so the web UI is reachable at http://<rpi-ip>/
    log "Installing system dependencies..."
    apt-get install -y --no-install-recommends \
        libxcb-cursor0 \
        xserver-xorg \
        xinit \
        x11-xserver-utils \
        unclutter \
        fonts-noto-color-emoji \
        nodejs \
        npm \
        nginx \
        2>/dev/null || warn "apt-get failed — install packages manually if needed"

    MODE=$(read_mode)
    log "Config mode: $MODE"

    # Web UI frontend build (best-effort; backend still works without it).
    build_web_frontend

    # Always install web backend + local UI (kiosk) services
    install_service "cdu-web-backend.service"
    install_service "cdu-local-ui.service"

    # Pushgateway: only install if its binary actually exists. The exporter
    # binary is not implemented yet (see docs / memory), so enabling the
    # service unconditionally would crash-loop (status=203/EXEC). Skip until ready.
    PUSHGATEWAY_BIN="/home/gadgetini/pushgateway/pushgateway"
    if [ -x "$PUSHGATEWAY_BIN" ]; then
        install_service "pushgateway.service"
    else
        warn "Pushgateway binary missing ($PUSHGATEWAY_BIN) — skipping service (re-run install once implemented)."
    fi

    # Mode-specific services
    if [ "$MODE" = "fake" ]; then
        install_service "cdu-fake-simulator.service"
        log "Fake simulator service installed."
    else
        install_service "cdu-mcg.service"
        log "MCG service installed."
    fi

    systemctl daemon-reload
    log "systemd daemon reloaded."

    # Enable + start installed services
    enable_service "cdu-web-backend.service"
    enable_service "cdu-local-ui.service"
    [ -x "$PUSHGATEWAY_BIN" ] && enable_service "pushgateway.service"

    if [ "$MODE" = "fake" ]; then
        enable_service "cdu-fake-simulator.service"
    else
        enable_service "cdu-mcg.service"
    fi

    # Kiosk: the X session + PySide6 UI is managed by cdu-local-ui.service
    # (xinit -> scripts/cdu_session.sh). No .bash_profile/.xinitrc needed.

    # Web service: reverse proxy so the UI is reachable at http://<rpi-ip>/
    install_nginx

    log ""
    log "Installation complete."
    log "Web UI:  http://<rpi-ip>/   (also http://<rpi-ip>:8000/ direct)"
    if [ "$MODE" = "fake" ]; then
        log "Start: sudo systemctl start cdu-fake-simulator"
    else
        log "Start: sudo systemctl start cdu-mcg"
    fi
}

build_web_frontend() {
    local fe="$PROJECT_ROOT/src/web_ui/frontend"
    if [ ! -f "$fe/package.json" ]; then
        warn "Frontend package.json missing at $fe — skipping build."
        return
    fi
    if ! command -v npm >/dev/null 2>&1; then
        warn "npm not available — skipping web frontend build. Install with: apt install npm"
        return
    fi
    log "Building Web UI frontend (npm ci && npm run build)..."
    (cd "$fe" && sudo -u "$USER" npm ci && sudo -u "$USER" npm run build) \
        || warn "Frontend build failed — backend will serve a 503 hint until built."
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

# ── Web service (nginx reverse proxy) ──────────────────────────────────────────

install_nginx() {
    local src="$PROJECT_ROOT/scripts/nginx/l2a-cdu.conf"
    local dst="/etc/nginx/sites-available/default"
    local link="/etc/nginx/sites-enabled/default"

    [ -f "$src" ] || { warn "nginx config not found: $src — skipping web proxy."; return; }
    command -v nginx >/dev/null 2>&1 || { warn "nginx not installed — skipping web proxy."; return; }

    # Back up any pre-existing site config that isn't already ours (one-time).
    if [ -f "$dst" ] && ! grep -q "L2A CDU Web UI" "$dst"; then
        local bak="${dst}.bak.$(date +%Y%m%d_%H%M%S)"
        cp "$dst" "$bak"
        log "Backed up existing nginx site → $bak"
    fi

    cp "$src" "$dst"
    ln -sf "$dst" "$link"
    log "Deployed nginx site → $dst"

    if nginx -t 2>/dev/null; then
        systemctl reload nginx 2>/dev/null || systemctl restart nginx 2>/dev/null || true
        systemctl enable nginx 2>/dev/null || true
        log "nginx reloaded (web UI at http://<rpi-ip>/)"
    else
        warn "nginx config test failed — leaving service untouched. Run 'sudo nginx -t' to debug."
    fi
}

# ── Status ────────────────────────────────────────────────────────────────────

do_status() {
    for svc in pushgateway.service cdu-fake-simulator.service cdu-mcg.service cdu-local-ui.service cdu-web-backend.service; do
        echo "─── $svc ───────────────────────────"
        systemctl status "$svc" --no-pager -l 2>/dev/null || echo "  (not installed)"
    done
}

# ── Stop ──────────────────────────────────────────────────────────────────────

do_stop() {
    require_root
    for svc in cdu-fake-simulator.service cdu-mcg.service cdu-web-backend.service cdu-local-ui.service; do
        systemctl stop "$svc" 2>/dev/null && log "Stopped $svc" || warn "$svc not running"
    done
}

# ── Remove ────────────────────────────────────────────────────────────────────

do_remove() {
    require_root
    for svc in cdu-fake-simulator.service cdu-mcg.service pushgateway.service cdu-web-backend.service cdu-local-ui.service; do
        systemctl stop    "$svc" 2>/dev/null || true
        systemctl disable "$svc" 2>/dev/null || true
        rm -f "$SERVICES_DST/$svc"
        log "Removed $svc"
    done
    systemctl daemon-reload
    log "Removal complete."
    log "Note: nginx site (/etc/nginx/sites-available/default) left in place — restore a .bak.* manually if needed."
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
