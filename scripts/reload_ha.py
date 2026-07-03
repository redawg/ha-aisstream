#!/usr/bin/env python3
"""Reload Home Assistant core to load new custom components."""
from __future__ import annotations

import json
import os
import sys
import time
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


def get(path: str, token: str):
    req = urllib.request.Request(f"{HA_URL}{path}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def post(path: str, token: str, payload: dict | None = None) -> tuple[int, str]:
    body = json.dumps(payload or {}).encode()
    req = urllib.request.Request(
        f"{HA_URL}{path}",
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def main() -> int:
    token = load_token()
    before = get("/api/config", token)
    print("before:", before.get("version"), "aisstream" in before.get("components", []))

    for service in (
        "/api/services/homeassistant/restart",
        "/api/services/homeassistant/reload_core_config",
    ):
        status, body = post(service, token)
        print(service, status, body[:120].replace("\n", " "))

    deadline = time.time() + 180
    while time.time() < deadline:
        try:
            config = get("/api/config", token)
            if config.get("state") == "RUNNING":
                loaded = "aisstream" in config.get("components", [])
                print("after:", config.get("version"), "aisstream loaded:", loaded)
                return 0 if loaded else 1
        except Exception:
            pass
        time.sleep(5)

    print("Timed out waiting for HA", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
