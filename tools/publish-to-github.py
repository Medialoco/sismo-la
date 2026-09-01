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
generous -- a quarter of an hour, not a minute.
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


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    snapshot = sys.argv[1]

    token = os.environ.get("SISMO_GITHUB_TOKEN")
    if not token:
        print("publish-to-github: SISMO_GITHUB_TOKEN is not set", file=sys.stderr)
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
    try:
        sha = _request(f"{url}?ref={branch}", token).get("sha")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            print(f"publish-to-github: cannot read current file: {exc}", file=sys.stderr)
            return 1

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
