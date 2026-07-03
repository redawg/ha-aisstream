#!/usr/bin/env python3
"""Probe Forest Home Assistant for deploy options."""
from __future__ import annotations

import json
import os
import sys
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
    auth = data["mcpServers"]["ha-forest"]["headers"]["Authorization"]
    return auth.split(" ", 1)[1].strip()


def get(path: str, token: str):
    req = urllib.request.Request(f"{HA_URL}{path}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    token = load_token()
    config = get("/api/config", token)
    print("location:", config.get("location_name"))
    print("version:", config.get("version"))
    print("components:", "hacs" in config.get("components", []))

    entries = get("/api/config/config_entries/entry", token)
    domains = sorted({e.get("domain") for e in entries})
    print("domains sample:", [d for d in domains if d in ("hacs", "aisstream", "life360")])

    for path in ("/api/hassio/addons", "/api/hassio/info"):
        try:
            data = get(path, token)
            if path.endswith("addons"):
                slugs = [
                    a["slug"]
                    for a in data.get("data", {}).get("addons", [])
                    if any(x in a["slug"].lower() for x in ("ssh", "terminal", "samba", "file", "hacs"))
                ]
                print("addons:", slugs)
            else:
                print("supervisor:", data.get("data", {}).get("version"))
        except urllib.error.HTTPError as exc:
            print(path, "HTTP", exc.code)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
