#!/usr/bin/env python3
"""Verify aisstream install and optionally start config flow."""
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
    return data["mcpServers"]["ha-forest"]["headers"]["Authorization"].split(" ", 1)[1].strip()


def req(method: str, path: str, token: str, payload: dict | None = None):
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        f"{HA_URL}{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = raw
        return exc.code, data


def main() -> int:
    token = load_token()
    config = req("GET", "/api/config", token)[1]
    print("components has aisstream:", "aisstream" in config.get("components", []))

    _, entries = req("GET", "/api/config/config_entries/entry", token)
    ais_entries = [e for e in entries if e.get("domain") == "aisstream"]
    print("aisstream entries:", len(ais_entries))
    for entry in ais_entries:
        print(" -", entry.get("title"), entry.get("entry_id"), entry.get("state"))

    status, flows = req("POST", "/api/config/config_entries/flow", token, {"handler": "aisstream"})
    print("config flow start:", status, flows)

    api_key = os.environ.get("AISSTREAM_API_KEY", "").strip()
    mmsi = os.environ.get("AISSTREAM_MMSI", "").strip()
    if api_key and mmsi and isinstance(flows, dict) and flows.get("flow_id"):
        status, step = req(
            "POST",
            f"/api/config/config_entries/flow/{flows['flow_id']}",
            token,
            {"api_key": api_key, "mmsi_list": mmsi},
        )
        print("config flow submit:", status, step)
    elif not ais_entries:
        print("Set AISSTREAM_API_KEY and AISSTREAM_MMSI to finish setup automatically.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
