#!/usr/bin/env bash
# Activate DEMO mode on this machine (a demo SD): mask the real cdu-mcg and run
# the fake-data seeder, so the UIs show stable demo values with no PCB attached.
#
# cdu-mcg MUST be masked — with no PCB it sets comm:status=disconnected and
# deletes the sensed keys, which would wipe the seeded values.
#
# Run once as root on the demo system:  sudo scripts/setup-demo.sh
# Revert with:                          sudo scripts/teardown-demo.sh
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "Run as root (sudo)." >&2; exit 1; }
HERE="$(cd "$(dirname "$0")/.." && pwd)"
UNIT="cdu-demo-seed.service"

echo ">>> Disabling + masking cdu-mcg (would clear seeded keys)..."
systemctl disable --now cdu-mcg.service 2>/dev/null || true
systemctl mask cdu-mcg.service

echo ">>> Installing ${UNIT}..."
cp "${HERE}/scripts/services/${UNIT}" "/etc/systemd/system/${UNIT}"
systemctl daemon-reload
systemctl enable --now "${UNIT}"

echo
echo ">>> Demo mode active: cdu-mcg masked, ${UNIT} running."
systemctl --no-pager --lines=0 status "${UNIT}" || true
echo ">>> Reboot to confirm fake data appears on boot."
