#!/usr/bin/env bash
# Activate DEMO mode on this machine (a demo SD): mask the real cdu-mcg and run
# the fake-data seeder, so the UIs show stable demo values with no PCB attached.
#
# cdu-mcg MUST be masked — with no PCB it sets comm:status=disconnected and
# deletes the sensed keys, which would wipe the seeded values.
#
# Idempotent: safe to re-run. The cdu-mcg stop/mask steps are best-effort
# (already-masked is fine); the seeder install ALWAYS runs and is verified.
#
# Run as root on the demo system:  sudo scripts/setup-demo.sh
# Revert with:                     sudo scripts/teardown-demo.sh

# NOTE: deliberately NOT using `set -e` — an already-masked cdu-mcg makes
# systemctl return non-zero, which must not abort the seeder install.
set -uo pipefail

[[ $EUID -eq 0 ]] || { echo "Run as root (sudo)." >&2; exit 1; }

HERE="$(cd "$(dirname "$0")/.." && pwd)"
UNIT="cdu-demo-seed.service"
SRC="${HERE}/scripts/services/${UNIT}"

if [[ ! -f "$SRC" ]]; then
    echo "ERROR: ${SRC} not found." >&2
    echo "       Are you on the 'demo' branch? (git checkout demo)" >&2
    exit 1
fi

echo ">>> Stopping + masking cdu-mcg (idempotent; it would clear seeded keys)..."
systemctl stop cdu-mcg.service 2>/dev/null || true
systemctl mask cdu-mcg.service 2>/dev/null || true
if [[ "$(systemctl is-enabled cdu-mcg.service 2>/dev/null)" == "masked" ]]; then
    echo "    cdu-mcg: masked OK"
else
    echo "    WARN: cdu-mcg not masked (active=$(systemctl is-active cdu-mcg.service 2>/dev/null)) — check manually" >&2
fi

echo ">>> Installing + starting ${UNIT}..."
cp "$SRC" "/etc/systemd/system/${UNIT}" || { echo "ERROR: copy failed: $SRC" >&2; exit 1; }
systemctl daemon-reload
systemctl enable "${UNIT}" 2>/dev/null || true
systemctl restart "${UNIT}"

sleep 1
if systemctl is-active --quiet "${UNIT}"; then
    echo ">>> OK: ${UNIT} is active — demo data seeding."
    echo ">>> Reboot to confirm fake data appears on boot."
else
    echo "ERROR: ${UNIT} failed to start. Inspect:" >&2
    echo "       journalctl -u ${UNIT} -n 30 --no-pager" >&2
    systemctl --no-pager --lines=10 status "${UNIT}" || true
    exit 1
fi
