#!/usr/bin/env python3
"""Publish the station snapshot into this repository, so GitHub Pages serves it.

The public page reads ``stations.json`` (the roster) and each node's
snapshot beside itself. This station writes ``web-remote/station.json``.
A second board sets ``SISMO_GITHUB_PATH`` to another file in ``web-remote/``
and gets its own row in the roster. Two boards must not share a path.

When the page is hosted on Pages, "beside itself" means a file committed to
``web-remote/`` -- so publishing a snapshot means writing a commit.

This uses the contents API rather than a git clone: the board needs no working
copy, no ssh key and no git identity, only a token. Give it a *fine-grained*
token restricted to this single repository with "Contents: read and write" and
nothing else; that is the least authority that can do the job, and it can be
revoked without touching anything else.

    export SISMO_GITHUB_TOKEN=github_pat_...
    tools/publish-to-github.py /tmp/station_xxx.json

Wired in through the ``publish.command`` block of ``python/config.yaml``.
Every snapshot is a commit that redeploys the page, so keep ``interval_s``
generous -- twenty minutes, not one. Pages tolerates roughly ten builds an
hour; three is comfortable. A snapshot whose only difference is the clock is
skipped, unless the last one is older than four hours: then it goes up
anyway, so a quiet night still leaves a heartbeat to read.

This tool publishes whatever JSON it is handed, verbatim. It does **not**
redact. The file it normally receives has already been through
``strip_watchlist`` / ``strip_confirmations`` / ``strip_location`` in
``python/main.py``; ``GET /api/state`` has not, and is the operator view --
station coordinates, catalog distances, per-event detection probabilities. So
piping the dashboard straight in here, as a way to publish immediately instead
of waiting for the timer, publishes the station's position.
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

API = "https://api.github.com"
# After this, an unchanged snapshot is still committed. The public page calls
# four hours without a file "offline"; a quiet station must beat that.
FORCE_AFTER_S = 4 * 3600


def _request(url: str, token: str, method: str = "GET", payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read() or b"{}")


def _token_files() -> list[str]:
    """Where the token may live when it does not come from the environment.

    App Lab generates the container's compose file from ``app.yaml``, which has
    no field for environment variables, and regenerates it on every app start --
    so there is no supported way to hand the container a secret through its
    environment. The app folder, however, is bind-mounted at /app, so a file
    dropped beside the code is visible inside. That is the route.

    ``APP_HOME`` is set by App Lab to the app's path *on the host*, which does
    not exist inside the container, so it cannot be the only candidate: the
    path relative to this file is what actually resolves under /app.
    """
    override = os.environ.get("SISMO_GITHUB_TOKEN_FILE")
    if override:
        return [override]
    roots = [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    app_home = os.environ.get("APP_HOME")
    if app_home and app_home not in roots:
        roots.append(app_home)
    return [os.path.join(r, ".sismo-token") for r in roots]


def _token() -> str | None:
    token = os.environ.get("SISMO_GITHUB_TOKEN")
    if token:
        return token.strip()
    for candidate in _token_files():
        try:
            with open(candidate, "r", encoding="utf-8") as fh:
                value = fh.read().strip()
        except OSError:
            continue
        if value:
            return value
    return None


def _same_but_for_time(old: bytes, new: bytes) -> bool:
    """True when two snapshots carry the same news.

    ``updated`` moves on its own, and the catalog block is refetched from the
    USGS on a timer, so both change without the station having observed
    anything. What matters is what the device did: its detections, its
    confirmed history, and the state of the models.

    ``confirmed`` is in the list because a retrospective confirmation is news --
    arguably the most interesting news this station can produce -- and it does
    not touch any of the other keys. Left out, a station whose only event of the
    week was found retrospectively would publish nothing at all.
    """
    keep = ("recent", "detections", "history", "confirmed", "calibration", "ai")
    try:
        a, b = json.loads(old), json.loads(new)
    except (ValueError, TypeError):
        return False
    return all(a.get(k) == b.get(k) for k in keep)


def _age_s(old: bytes) -> float | None:
    """Seconds since the last snapshot's own ``updated`` field."""
    try:
        stamp = json.loads(old).get("updated")
        if not stamp:
            return None
        t = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - t).total_seconds()
    except (ValueError, TypeError):
        return None


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    snapshot = sys.argv[1]

    token = _token()
    if not token:
        where = " or ".join(_token_files())
        print(f"publish-to-github: no token. Set SISMO_GITHUB_TOKEN, or write it "
              f"to {where} (chmod 600).", file=sys.stderr)
        return 1

    repo = os.environ.get("SISMO_GITHUB_REPO", "Medialoco/sismo-la")
    path = os.environ.get("SISMO_GITHUB_PATH", "web-remote/station.json")
    branch = os.environ.get("SISMO_GITHUB_BRANCH", "main")
    url = f"{API}/repos/{repo}/contents/{path}"

    try:
        with open(snapshot, "rb") as fh:
            body = fh.read()
    except OSError as exc:
        print(f"publish-to-github: cannot read {snapshot}: {exc}", file=sys.stderr)
        return 1

    # Updating a file requires the blob SHA of the version being replaced; its
    # absence simply means the file does not exist yet, which is the first run.
    sha = None
    current = None
    try:
        info = _request(f"{url}?ref={branch}", token)
        sha = info.get("sha")
        if info.get("encoding") == "base64":
            current = base64.b64decode(info.get("content", ""))
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            print(f"publish-to-github: cannot read current file: {exc}", file=sys.stderr)
            return 1

    # A station that detects nothing for a week would otherwise commit an
    # identical snapshot every twenty minutes, purely because the clock moved.
    # Skip those — unless the last file is old enough that the public page
    # would call the station offline, or that there is nothing recent to
    # analyse. Then send a heartbeat anyway.
    if current is not None and _same_but_for_time(current, body):
        age = _age_s(current)
        if age is None or age >= FORCE_AFTER_S:
            hours = (age / 3600.0) if age is not None else float("inf")
            print(f"publish-to-github: unchanged, but last snapshot "
                  f"{hours:.1f}h ago — committing heartbeat")
        else:
            print("publish-to-github: unchanged since last snapshot, not committing")
            return 0

    # Without an explicit author the commit is attributed to whatever profile
    # name the token's account carries, which is not the identity the rest of
    # the history uses.
    who = {
        "name": os.environ.get("SISMO_GIT_NAME", "thepriben"),
        "email": os.environ.get(
            "SISMO_GIT_EMAIL", "5019565+thepriben@users.noreply.github.com"
        ),
    }
    payload = {
        "message": "Publish station snapshot",
        "content": base64.b64encode(body).decode(),
        "branch": branch,
        "author": who,
        "committer": who,
    }
    if sha:
        payload["sha"] = sha

    try:
        _request(url, token, method="PUT", payload=payload)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        print(f"publish-to-github: {exc.code} {exc.reason} -- {detail}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"publish-to-github: network error: {exc.reason}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
