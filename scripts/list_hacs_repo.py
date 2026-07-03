#!/usr/bin/env python3
"""List HACS repos matching a query."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import aiohttp

HA_URL = os.environ.get("HA_URL", "http://172.16.255.250:8123").rstrip("/")
HA_WS = HA_URL.replace("http://", "ws://") + "/api/websocket"
QUERY = os.environ.get("QUERY", "aisstream").lower()
MCP_JSON = Path.home() / ".cursor" / "mcp.json"


def load_token() -> str:
    token = os.environ.get("HA_TOKEN", "").strip()
    if token:
        return token
    data = json.loads(MCP_JSON.read_text(encoding="utf-8"))
    return data["mcpServers"]["ha-forest"]["headers"]["Authorization"].split(" ", 1)[1].strip()


async def main() -> None:
    token = load_token()
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(HA_WS, timeout=60) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": token})
            await ws.receive_json()
            await ws.send_json({"id": 1, "type": "hacs/repositories/list"})
            while True:
                msg = await ws.receive_json()
                if msg.get("id") == 1:
                    repos = msg.get("result", [])
                    break

    matches = [
        r for r in repos
        if QUERY in str(r.get("full_name", "")).lower()
        or QUERY in str(r.get("name", "")).lower()
        or QUERY in str(r.get("domain", "")).lower()
    ]
    print(f"matches for {QUERY!r}: {len(matches)}")
    for r in matches:
        print(json.dumps({
            "id": r.get("id"),
            "full_name": r.get("full_name"),
            "installed": r.get("installed"),
            "installed_version": r.get("installed_version"),
            "custom": r.get("custom"),
            "status": r.get("status"),
            "local_path": r.get("local_path"),
        }))


if __name__ == "__main__":
    asyncio.run(main())
