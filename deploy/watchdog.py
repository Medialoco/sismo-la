#!/usr/bin/env python3
"""Keep the Sismo-LA container running across reboots.

Why this exists, in one paragraph. At boot, dockerd loads its containers and
honours their restart policy, so the app container *is* started -- and then,
one second later, the ``arduino-app-cli`` daemon starts and stops it again,
because App Lab has no notion of an app that should still be running. Docker
records that stop as deliberate (``hasBeenManuallyStopped=true``), so from the
*next* boot onwards ``unless-stopped`` declines to start it at all and the
station is permanently dead until someone plugs a cable in. Observed on the
reference board on 2026-08-31, twice, with the timestamps to match.

The fix is to start the app *after* the daemon has had its say. Cron would be
the obvious tool and is unusable here: the ``arduino`` account's password is
expired, so PAM refuses its jobs. What is left, and what this uses, is Docker
itself -- dockerd runs as root from boot and never consults PAM. This script
runs in a tiny sidecar container with ``--restart always``, waits out the
reconcile, then keeps the app container up.

It talks to the Docker socket directly over HTTP rather than shelling out, so
the image needs nothing but a Python interpreter.

Deliberately stopping the station stays possible: create ``.autostart-disabled``
in the app folder and this loop keeps its hands off.
"""

import http.client
import json
import os
import socket
import sys
import time

SOCKET = "/var/run/docker.sock"
TARGET = os.environ.get("SISMO_CONTAINER", "sismo-la-main-1")
STATION = os.environ.get("SISMO_STATION_DIR", "/station")
# arduino-app-cli stops the container about one second after dockerd starts it.
# Anything comfortably past that works; this also leaves room for a slow boot.
FIRST_DELAY = float(os.environ.get("SISMO_FIRST_DELAY", "150"))
PERIOD = float(os.environ.get("SISMO_PERIOD", "60"))


class DockerSocket(http.client.HTTPConnection):
    def __init__(self, path: str = SOCKET) -> None:
        super().__init__("localhost")
        self._path = path

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(20)
        sock.connect(self._path)
        self.sock = sock


def _call(method: str, path: str):
    conn = DockerSocket()
    try:
        conn.request(method, path)
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, body
    finally:
        conn.close()


def state() -> str:
    """"running", "exited", "absent", or "unknown" when the socket misbehaves."""
    try:
        status, body = _call("GET", f"/containers/{TARGET}/json")
    except OSError as exc:
        log(f"docker socket unreachable: {exc}")
        return "unknown"
    if status == 404:
        return "absent"
    if status != 200:
        log(f"unexpected status {status} inspecting {TARGET}")
        return "unknown"
    try:
        return json.loads(body)["State"]["Status"]
    except (ValueError, KeyError):
        return "unknown"


def start() -> bool:
    try:
        status, body = _call("POST", f"/containers/{TARGET}/start")
    except OSError as exc:
        log(f"start failed: {exc}")
        return False
    if status in (204, 304):
        return True
    log(f"start refused ({status}): {body.decode(errors='replace')[:200]}")
    return False


def disabled() -> bool:
    return os.path.exists(os.path.join(STATION, ".autostart-disabled"))


def log(msg: str) -> None:
    print(f"[watchdog] {time.strftime('%Y-%m-%d %H:%M:%S')} {msg}", flush=True)


def main() -> int:
    log(f"up; watching {TARGET}, first check in {FIRST_DELAY:.0f}s")
    time.sleep(FIRST_DELAY)
    while True:
        if disabled():
            log("autostart disabled by .autostart-disabled, standing by")
        else:
            current = state()
            if current == "absent":
                # Only arduino-app-cli can recreate a container it removed, and
                # it is not reachable from in here. Say so rather than spin.
                log(f"{TARGET} does not exist -- run `arduino-app-cli app start`")
            elif current not in ("running", "restarting", "unknown"):
                log(f"{TARGET} is {current}, starting it")
                if start():
                    log(f"{TARGET} started")
        time.sleep(PERIOD)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
