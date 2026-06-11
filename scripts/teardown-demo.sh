#!/usr/bin/env bash
# Revert DEMO mode: stop the fake-data seeder and restore the real cdu-mcg.
# Idempotent: safe to re-run (already-unmasked etc. is fine).
# Run as root:  sudo scripts/teardown-demo.sh
set -uo pipefail

[[ $EUID -eq 0 ]] || { echo "Run as root (sudo)." >&2; exit 1; }
UNIT="cdu-demo-seed.service"

echo ">>> Stopping + disabling ${UNIT}..."
systemctl disable --now "${UNIT}" 2>/dev/null || true

echo ">>> Unmasking + restoring cdu-mcg..."
systemctl unmask cdu-mcg.service 2>/dev/null || true
systemctl enable cdu-mcg.service 2>/dev/null || true
systemctl restart cdu-mcg.service 2>/dev/null || true

echo ">>> Done. cdu-mcg active=$(systemctl is-active cdu-mcg.service 2>/dev/null), demo-seed active=$(systemctl is-active ${UNIT} 2>/dev/null)"
echo "    (Seeded keys clear automatically once cdu-mcg hits disconnected.)"
