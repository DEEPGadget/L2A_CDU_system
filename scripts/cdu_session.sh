#!/bin/bash
# cdu_session.sh — X session script for the L2A CDU kiosk.
#
# Launched by `xinit` from cdu-local-ui.service. The X server is already
# running when this script starts. We set up the X session, then loop the
# Python UI so an app crash only restarts the app — the X server stays up.

set -u

exec > >(systemd-cat -t cdu-session) 2>&1

VENV_PYTHON="/home/gadgetini/venv/bin/python"
APP_MAIN="/home/gadgetini/L2A_CDU_system/src/local_ui/main.py"

echo "[cdu_session] X session entered at $(date +%s.%N)"

xset s off
xset -dpms
xset s noblank

xsetroot -solid black

unclutter -idle 0 -root &

while true; do
    echo "[cdu_session] launching python at $(date +%s.%N)"
    "$VENV_PYTHON" "$APP_MAIN"
    sleep 2
done
