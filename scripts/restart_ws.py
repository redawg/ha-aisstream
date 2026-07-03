#!/usr/bin/env python3
"""Restart HA via WebSocket service call."""
from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.request
from pathlib import Path

import aiohttp

HA_URL = os.environ.get("HA_URL", "http://172.16.255.250:8123").rstrip("/")
HA_WS = HA_URL.replace("http://", "ws://") + "/api/websocket"
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
            print("auth:", (await ws.receive_json()).get("type"))
            await ws.send_json({
                "id": 1,
                "type": "call_service",
                "domain": "homeassistant",
                "service": "restart",
                "service_data": {},
            })
            print("restart:", await ws.receive_json())

    deadline = time.time() + 180
    while time.time() < deadline:
        try:
            req = urllib.request.Request(
                f"{HA_URL}/api/config",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                config = json.loads(resp.read().decode())
            if config.get("state") == "RUNNING":
                print("loaded aisstream:", "aisstream" in config.get("components", []))
                return
        except Exception:
            pass
        time.sleep(5)
    print("timed out")


if __name__ == "__main__":
    asyncio.run(main())
