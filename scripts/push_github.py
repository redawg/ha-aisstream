#!/usr/bin/env python3
"""Push integration files to GitHub via API using gh token from MCP or env."""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OWNER = os.environ.get("GITHUB_OWNER", "sh00t2kill")
REPO = os.environ.get("GITHUB_REPO", "ha-aisstream")
BRANCH = os.environ.get("GITHUB_BRANCH", "main")
MESSAGE = os.environ.get(
    "GITHUB_COMMIT_MESSAGE",
    "Add Seattle area tracking for Puget Sound vessels (v1.1.0)",
)

FILES = [
    "custom_components/aisstream/__init__.py",
    "custom_components/aisstream/coordinator.py",
    "custom_components/aisstream/config_flow.py",
    "custom_components/aisstream/const.py",
    "custom_components/aisstream/device_tracker.py",
    "custom_components/aisstream/manifest.json",
    "custom_components/aisstream/strings.json",
]


def load_token() -> str:
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        token = os.environ.get(key, "").strip()
        if token:
            return token
    raise SystemExit("Set GITHUB_TOKEN or GH_TOKEN")


def api_request(method: str, url: str, token: str, payload: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "ha-aisstream-push",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode()
            return resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = body
        raise RuntimeError(f"{method} {url} -> {exc.code}: {parsed}") from exc


def get_sha(token: str, path: str) -> str | None:
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}?ref={BRANCH}"
    try:
        _, data = api_request("GET", url, token)
        return data.get("sha") if isinstance(data, dict) else None
    except RuntimeError as exc:
        if "404" in str(exc):
            return None
        raise


def main() -> int:
    token = load_token()
    for rel in FILES:
        path = ROOT / rel
        content_b64 = base64.b64encode(path.read_bytes()).decode()
        payload = {
            "message": MESSAGE,
            "content": content_b64,
            "branch": BRANCH,
        }
        sha = get_sha(token, rel.replace("\\", "/"))
        if sha:
            payload["sha"] = sha
        url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{rel.replace('\\', '/')}"
        status, result = api_request("PUT", url, token, payload)
        print(f"updated {rel}: HTTP {status}")
        if isinstance(result, dict):
            print("  commit:", result.get("commit", {}).get("sha", "")[:12])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
