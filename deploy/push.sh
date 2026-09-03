#!/usr/bin/env bash
# Deploy the Python half of the station over the LAN, with no USB cable.
#
#   deploy/push.sh [host]
#
# Why this is not "just scp": the board's app folder holds files that only
# exist there and must never be overwritten -- python/config.yaml (the real
# station position), .sismo-token, event_log.jsonl (the whole ambient-noise
# record) and the model state files. Sending only git-tracked files makes that
# impossible by construction rather than by care.
#
# What it deliberately does NOT do is touch the microcontroller. A Python-side
# change needs `docker restart`, which reloads the config and the code while
# leaving the MCU running; `arduino-app-cli app restart` would halt the MCU and
# nothing in the recovery path starts it again. A sketch change still needs USB.

set -euo pipefail

HOST="${1:-192.168.1.69}"
KEY="${SISMO_SSH_KEY:-$HOME/.ssh/id_ed25519_sismo}"
APP="/home/arduino/ArduinoApps/sismo-la"
SSH=(ssh -i "$KEY" -o ConnectTimeout=10 "arduino@$HOST")

cd "$(dirname "$0")/.."

echo "== sending tracked files to $HOST =="
git ls-files -z python/ deploy/ tools/ \
  | COPYFILE_DISABLE=1 tar -cf - --null -T - \
  | "${SSH[@]}" "cat > /tmp/sismo-payload.tar && cd $APP && tar -xf /tmp/sismo-payload.tar && rm /tmp/sismo-payload.tar && echo extracted"

echo
echo "== restarting the container (the MCU keeps running) =="
"${SSH[@]}" "docker restart sismo-la-main-1"

echo
echo "== waiting for the app to come back =="
# Waiting for the HTTP server is not enough and is the exact trap that once
# made a blind station look healthy: the dashboard runs in its own thread and
# answers long before the MCU has said anything. Wait for a heartbeat instead,
# which arrives every 10 s and is the only independent evidence the sensor is
# alive.
for i in $(seq 1 30); do
  if "${SSH[@]}" "curl -sf -m 3 http://localhost:8000/api/state" 2>/dev/null \
     | grep -q '"mcu_ok": *true'; then
    echo "MCU heartbeat received after ~$((i * 2))s"
    break
  fi
  sleep 2
done

echo
echo "== health =="
"${SSH[@]}" "curl -s http://localhost:8000/api/state" | python3 -c "
import sys, json
s = json.load(sys.stdin)
h = s.get('health', {})
print('mcu_ok', h.get('mcu_ok'), '| silent', h.get('mcu_silent_s'), 's | stale', h.get('stale'))
print('problems:', h.get('problems'))
print('detail:', h.get('mcu_last_detail'))
"

echo
echo "If mcu_ok is False the microcontroller is not running, and that cannot be"
echo "fixed over the network: reflashing needs USB."
