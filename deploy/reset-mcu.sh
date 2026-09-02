#!/usr/bin/env bash
# Restart the microcontroller over the network, with no USB cable.
#
#   deploy/reset-mcu.sh [host]
#
# Use it when the station answers on port 8000 but reports `mcu_ok: false` --
# the dashboard is alive and the sensor is not, which is the station's most
# dangerous failure mode because everything that answers a request looks fine.
#
# How it works. `arduino-router` drives the STM32's reset line: its after-ready
# command is `gpioset -c /dev/gpiochip1 -t0 70=1`. Restarting the service
# therefore resets the MCU, which reboots into the sketch already in its flash
# -- no flashing involved, so no cable.
#
# The second step is not optional. Restarting the router creates a NEW
# /var/run/arduino-router.sock, while the app container still has the old inode
# bind-mounted; the Bridge then loops on "Failed to connect to router:
# [Errno 111] Connection refused" forever. Restarting the container rebinds it.
#
# Root comes from the docker group, not from a password: dockerd runs as root,
# and `--user 0:0` overrides the image's pinned non-root user.
#
# This does NOT replace flashing. If the sketch itself needs to change, or if
# the MCU stays silent after this, the cable is still required.

set -euo pipefail

HOST="${1:-192.168.1.69}"
KEY="${SISMO_SSH_KEY:-$HOME/.ssh/id_ed25519_sismo}"
IMAGE="ghcr.io/arduino/app-bricks/python-apps-base:0.10.1"
SSH=(ssh -i "$KEY" -o ConnectTimeout=10 "arduino@$HOST")

echo "== resetting the MCU via the router =="
"${SSH[@]}" "docker run --rm --privileged --pid=host --user 0:0 --entrypoint sh $IMAGE \
  -c 'nsenter -t 1 -m -u -i -n -p -- systemctl restart arduino-router'"

sleep 10

echo "== rebinding the app to the new router socket =="
"${SSH[@]}" "docker restart sismo-la-main-1"

echo "== waiting for a heartbeat =="
for i in $(seq 1 40); do
  if "${SSH[@]}" "curl -sf -m 3 http://localhost:8000/api/state" 2>/dev/null \
     | grep -q '"mcu_ok": *true'; then
    echo "MCU alive after ~$((i * 3))s"
    "${SSH[@]}" "curl -s http://localhost:8000/api/state" | python3 -c "
import sys, json
h = json.load(sys.stdin)['health']
print('detail:', h.get('mcu_last_detail'))
"
    exit 0
  fi
  sleep 3
done

echo "MCU still silent after 2 minutes. This needs the USB cable:"
echo "  arduino-cli compile --profile default --upload ./sketch -p /dev/cu.usbmodem*"
exit 1
