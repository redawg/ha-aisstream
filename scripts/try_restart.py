#!/usr/bin/env python3
"""Try supervisor/core restart endpoints."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

HA_URL = os.environ.get("HA_URL", "http://172.16.255.250:8123").rstrip("/")
MCP_JSON = Path.home() / ".cursor" / "mcp.json"


def load_token() -> str:
    token = os.environ.get("HA_TOKEN", "").strip()
    if token:
        return token
    data = json.loads(MCP_JSON.read_text(encoding="utf-8"))
    return data["mcpServers"]["ha-forest"]["headers"]["Authorization"].split(" ", 1)[1].strip()


def post(path: str, token: str) -> None:
    req = urllib.request.Request(
        f"{HA_URL}{path}",
        data=b"{}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            print(path, resp.status, resp.read().decode()[:200])
    except urllib.error.HTTPError as exc:
        print(path, exc.code, exc.read().decode()[:200])


def main() -> None:
    token = load_token()
    for path in (
        "/api/hassio/core/restart",
        "/api/hassio/host/reboot",
        "/api/services/homeassistant/restart",
    ):
        post(path, token)


if __name__ == "__main__":
    main()
