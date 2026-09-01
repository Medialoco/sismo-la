#!/usr/bin/env python3
"""Publish the station snapshot into this repository, so GitHub Pages serves it.

The public page reads ``station.json`` from beside itself. When the page is
hosted on Pages, "beside itself" means a file committed to ``web-remote/`` --
so publishing a snapshot means writing a commit.

This uses the contents API rather than a git clone: the board needs no working
copy, no ssh key and no git identity, only a token. Give it a *fine-grained*
token restricted to this single repository with "Contents: read and write" and
nothing else; that is the least authority that can do the job, and it can be
revoked without touching anything else.

    export SISMO_GITHUB_TOKEN=github_pat_...
    tools/publish-to-github.py /tmp/station_xxx.json

Wired in through the ``publish.command`` block of ``python/config.yaml``.
Every snapshot is a commit that redeploys the page, so keep ``interval_s``
generous -- half an hour, not a minute. A snapshot whose only difference is
the clock is skipped, so a quiet station stops committing altogether.
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"


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


def _token_file() -> str:
    """Where the token lives when it does not come from the environment.

    App Lab generates the container's compose file from ``app.yaml``, which has
    no field for environment variables, and regenerates it on every app start --
    so there is no supported way to hand the container a secret through its
    environment. The app folder, however, is bind-mounted at /app, so a file
    dropped beside the code is visible inside. That is the route.
    """
    override = os.environ.get("SISMO_GITHUB_TOKEN_FILE")
    if override:
        return override
    root = os.environ.get("APP_HOME") or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
    return os.path.join(root, ".sismo-token")


def _token() -> str | None:
    token = os.environ.get("SISMO_GITHUB_TOKEN")
    if token:
        return token.strip()
    try:
        with open(_token_file(), "r", encoding="utf-8") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def _same_but_for_time(old: bytes, new: bytes) -> bool:
    """True when two snapshots carry the same news.

    ``updated`` moves on its own, and the catalog block is refetched from the
    USGS on a timer, so both change without the station having observed
    anything. What matters is what the device did: its detections, its
    confirmed history, and the state of the models.
    """
    keep = ("detections", "history", "calibration", "ai")
    try:
        a, b = json.loads(old), json.loads(new)
    except (ValueError, TypeError):
        return False
    return all(a.get(k) == b.get(k) for k in keep)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    snapshot = sys.argv[1]

    token = _token()
    if not token:
        print(f"publish-to-github: no token. Set SISMO_GITHUB_TOKEN, or write it "
              f"to {_token_file()} (chmod 600).", file=sys.stderr)
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
    # identical snapshot every half hour, purely because the clock moved. Two
    # snapshots that differ only by their timestamp are not news.
    if current is not None and _same_but_for_time(current, body):
        print("publish-to-github: unchanged since last snapshot, not committing")
        return 0

    payload = {
        "message": "Publish station snapshot",
        "content": base64.b64encode(body).decode(),
        "branch": branch,
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
