#!/usr/bin/env python3
"""Configure AISstream on Forest Home."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HA_URL = os.environ.get("HA_URL", "http://172.16.255.250:8123").rstrip("/")
MCP_JSON = Path.home() / ".cursor" / "mcp.json"

WSF_MMSIS = (
    "366709770,366709780,366710820,366749710,366759130,366772750,366772760,"
    "366772780,366772960,366772980,366772990,366773040,366773070,366773090,"
    "367463060,367479990,367480010,367608860,367649320,367712660,368027230"
)


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
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
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
    api_key = os.environ.get("AISSTREAM_API_KEY", "").strip()
    if not api_key:
        print("AISSTREAM_API_KEY required", file=sys.stderr)
        return 1

    token = load_token()
    _, entries = req("GET", "/api/config/config_entries/entry", token)
    existing = [e for e in entries if e.get("domain") == "aisstream"]
    if existing:
        print("aisstream already configured:", existing[0].get("title"))
        return 0

    status, flow = req("POST", "/api/config/config_entries/flow", token, {"handler": "aisstream"})
    if status != 200 or not isinstance(flow, dict) or not flow.get("flow_id"):
        print("failed to start flow:", status, flow, file=sys.stderr)
        return 1

    payload = {
        "api_key": api_key,
        "mmsi_list": os.environ.get("AISSTREAM_MMSI", WSF_MMSIS),
        "track_area": True,
    }
    status, result = req(
        "POST",
        f"/api/config/config_entries/flow/{flow['flow_id']}",
        token,
        payload,
    )
    print("configure:", status, result)
    return 0 if status == 200 and isinstance(result, dict) and result.get("type") == "create_entry" else 1


if __name__ == "__main__":
    raise SystemExit(main())
