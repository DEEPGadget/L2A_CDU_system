#!/usr/bin/env bash
# Revert DEMO mode: stop the fake-data seeder and restore the real cdu-mcg.
# Run as root:  sudo scripts/teardown-demo.sh
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "Run as root (sudo)." >&2; exit 1; }
UNIT="cdu-demo-seed.service"

echo ">>> Stopping + disabling ${UNIT}..."
systemctl disable --now "${UNIT}" 2>/dev/null || true

echo ">>> Unmasking + restoring cdu-mcg..."
systemctl unmask cdu-mcg.service
systemctl enable --now cdu-mcg.service

echo ">>> Real MCG restored. (Seeded keys clear on the next disconnect cycle.)"
