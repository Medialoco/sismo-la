#!/usr/bin/env python3
"""Keep the Sismo-LA station running -- both halves of it -- across reboots.

Why this exists, in one paragraph. At boot, dockerd loads its containers and
honours their restart policy, so the app container *is* started -- and then,
one second later, the ``arduino-app-cli`` daemon starts and stops it again,
because App Lab has no notion of an app that should still be running. Docker
records that stop as deliberate (``hasBeenManuallyStopped=true``), so from the
*next* boot onwards ``unless-stopped`` declines to start it at all and the
station is permanently dead until someone plugs a cable in. Observed on the
reference board on 2026-08-31, twice, with the timestamps to match.

The second half of the problem, measured on 2026-09-01. This watchdog used to
recover the station with ``docker start``, which brings the container back and
*leaves the microcontroller empty*. App Lab's own API documents why:

    POST /v1/apps/{id}/stop   "If the app contains a sketch it also remove it
                               from the micro."
    POST /v1/apps/{id}/start  "If the app contains a sketch it also flash it
                               in the micro."

So App Lab's boot-time stop does not merely halt the sketch, it erases it. A
``docker start`` then returns a station that serves a dashboard, answers every
request, and cannot feel a thing -- which is worse than one that is plainly
off, because it looks alive. The only way back is a flash, and the only flasher
reachable without root is that same daemon, on 127.0.0.1:8800. Hence
``--network host`` on this sidecar, and hence recovery goes through the API
with ``docker start`` kept only as a last resort.

Cron would be the natural tool for the boot delay and is unusable here: the
``arduino`` account's password is expired, so PAM refuses every job it owns.
What is left is Docker itself -- dockerd runs as root from boot and never
consults PAM. This runs in a tiny sidecar with ``--restart always``, waits out
the App Lab reconcile, then keeps both halves up.

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
APP_NAME = os.environ.get("SISMO_APP_NAME", "sismo-la")
APPLAB = os.environ.get("SISMO_APPLAB", "127.0.0.1:8800")
DASHBOARD = os.environ.get("SISMO_DASHBOARD", "127.0.0.1:8000")

# arduino-app-cli stops the container about one second after dockerd starts it.
# Anything comfortably past that works; this also leaves room for a slow boot.
FIRST_DELAY = float(os.environ.get("SISMO_FIRST_DELAY", "150"))
PERIOD = float(os.environ.get("SISMO_PERIOD", "60"))

# How long the MCU may stay silent before we treat it as gone. Deliberately far
# above the 10 s heartbeat: a flash takes ~3 min, during which the MCU is
# legitimately quiet, and recovering costs another 3 min of downtime. Being
# slow here is much cheaper than a station that reflashes itself in a loop.
MCU_SILENT_LIMIT = float(os.environ.get("SISMO_MCU_SILENT_LIMIT", "900"))
COOLDOWN = float(os.environ.get("SISMO_COOLDOWN", "1800"))
# If the sketch is flashed and the MCU still says nothing, the fault is
# physical (an unseated Qwiic cable, a dead board) and reflashing will not fix
# it. Give up after a few tries rather than disrupt the station every 30 min
# forever; the dashboard's red banner is then the thing that asks for a human.
MAX_MCU_ATTEMPTS = int(os.environ.get("SISMO_MAX_MCU_ATTEMPTS", "3"))


def log(msg: str) -> None:
    print(f"[watchdog] {time.strftime('%Y-%m-%d %H:%M:%S')} {msg}", flush=True)


# --- Docker, over its unix socket -----------------------------------------

class DockerSocket(http.client.HTTPConnection):
    def __init__(self, path: str = SOCKET) -> None:
        super().__init__("localhost")
        self._path = path

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(20)
        sock.connect(self._path)
        self.sock = sock


def _docker(method: str, path: str):
    conn = DockerSocket()
    try:
        conn.request(method, path)
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def container_state() -> str:
    """"running", "exited", "absent", or "unknown" when the socket misbehaves."""
    try:
        status, body = _docker("GET", f"/containers/{TARGET}/json")
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


def docker_start() -> bool:
    """Last-resort start. Brings the dashboard back but NOT the sketch."""
    try:
        status, body = _docker("POST", f"/containers/{TARGET}/start")
    except OSError as exc:
        log(f"docker start failed: {exc}")
        return False
    if status in (204, 304):
        return True
    log(f"docker start refused ({status}): {body.decode(errors='replace')[:200]}")
    return False


# --- App Lab daemon, over 127.0.0.1 (needs --network host) -----------------

def _applab(method: str, path: str, timeout: float):
    host, _, port = APPLAB.partition(":")
    conn = http.client.HTTPConnection(host, int(port or 80), timeout=timeout)
    try:
        conn.request(method, path)
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def app_id() -> str:
    """App Lab's identifier for our app (a base64 of "user:<name>")."""
    status, body = _applab("GET", "/v1/apps", 20)
    if status != 200:
        raise RuntimeError(f"/v1/apps returned {status}")
    apps = json.loads(body)
    if isinstance(apps, dict):
        apps = apps.get("apps", [])
    for a in apps:
        if a.get("name") == APP_NAME:
            return a["id"]
    raise RuntimeError(f"no app named {APP_NAME!r} in /v1/apps")


def applab_start() -> bool:
    """Start the app through App Lab, which also flashes the sketch.

    The response is a Server-Sent Events stream that stays open for the whole
    build-and-flash, so this blocks for minutes by design.
    """
    try:
        ident = app_id()
    except Exception as exc:
        log(f"cannot reach the App Lab daemon on {APPLAB}: {exc}")
        return False
    log(f"asking App Lab to start {APP_NAME} (id {ident}); this also flashes "
        f"the sketch, expect ~3 min")
    try:
        status, body = _applab("POST", f"/v1/apps/{ident}/start", 900)
    except Exception as exc:
        log(f"App Lab start failed: {exc}")
        return False
    if status != 200:
        text = body.decode(errors="replace")
        log(f"App Lab start refused ({status}): {text[:300]}")
        return False
    # Judge by the outcome, not by the stream. The SSE body relays the flasher's
    # own chatter and always ends on a close event, so scanning it for the word
    # "error" is unreliable: the first version of this reported a failed start
    # on OpenOCD's "Info : device idcode = 0x30076482" line while the recovery
    # had in fact succeeded.
    for _ in range(30):
        if container_state() == "running":
            return True
        time.sleep(2)
    log("App Lab start returned but the container is still not running")
    return False


# --- Station health --------------------------------------------------------

def mcu_silent_seconds():
    """Seconds since the MCU last spoke, or None if that cannot be judged.

    Reads the station's own health block. None means "do not act": the app is
    not answering yet, is too old to publish health, or is in a mode where
    there is no MCU to lose.
    """
    host, _, port = DASHBOARD.partition(":")
    try:
        conn = http.client.HTTPConnection(host, int(port or 80), timeout=10)
        try:
            conn.request("GET", "/api/state")
            resp = conn.getresponse()
            if resp.status != 200:
                return None
            health = json.loads(resp.read()).get("health")
        finally:
            conn.close()
    except Exception:
        return None
    if not health or not health.get("mcu_expected", False):
        return None
    return health.get("mcu_silent_s")


def disabled() -> bool:
    return os.path.exists(os.path.join(STATION, ".autostart-disabled"))


def main() -> int:
    log(f"up; watching {TARGET} and its MCU, first check in {FIRST_DELAY:.0f}s")
    time.sleep(FIRST_DELAY)
    last_recovery = 0.0
    mcu_attempts = 0

    while True:
        if disabled():
            log("autostart disabled by .autostart-disabled, standing by")
            time.sleep(PERIOD)
            continue

        reason = None
        current = container_state()
        if current in ("absent", "exited", "created", "dead", "paused"):
            # "absent" is recoverable now: App Lab recreates the container.
            reason = f"container is {current}"
        elif current == "running":
            silent = mcu_silent_seconds()
            if silent is not None and silent > MCU_SILENT_LIMIT:
                if mcu_attempts >= MAX_MCU_ATTEMPTS:
                    log(f"MCU silent {silent:.0f}s but {mcu_attempts} reflashes "
                        f"have not fixed it -- looks physical, leaving it to a "
                        f"human")
                else:
                    reason = f"MCU silent for {silent:.0f}s"
            elif silent is not None:
                mcu_attempts = 0  # the MCU is talking again

        if reason:
            since = time.monotonic() - last_recovery
            if last_recovery and since < COOLDOWN:
                log(f"{reason}, but last recovery was {since:.0f}s ago "
                    f"(cooldown {COOLDOWN:.0f}s)")
            else:
                log(f"{reason}; recovering")
                if reason.startswith("MCU"):
                    mcu_attempts += 1
                last_recovery = time.monotonic()
                if applab_start():
                    log("App Lab start finished (container + sketch)")
                elif container_state() != "running" and docker_start():
                    # Better than nothing: the dashboard comes back and its red
                    # banner reports the MCU is still down.
                    log("fell back to docker start -- dashboard only, MCU still "
                        "unflashed")

        time.sleep(PERIOD)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
