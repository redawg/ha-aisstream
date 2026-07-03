#!/usr/bin/env python3
"""Debug HACS WebSocket commands on Forest HA."""
from __future__ import annotations

import asyncio
import json
import os
import sys
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


async def main() -> int:
    token = load_token()
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(HA_WS, timeout=60) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": token})
            auth = await ws.receive_json()
            print("auth:", auth.get("type"))

            msg_id = 1
            for payload in [
                {"type": "hacs/info"},
                {"type": "hacs/repositories", "categories": ["integration"]},
                {"type": "hacs/repositories/list"},
                {"type": "hacs/repository/add", "repository": "https://github.com/sh00t2kill/ha-aisstream", "category": "integration"},
                {"type": "hacs/repository/add", "repository": "sh00t2kill/ha-aisstream", "category": "integration"},
            ]:
                await ws.send_json({"id": msg_id, **payload})
                while True:
                    msg = await ws.receive_json()
                    if msg.get("id") == msg_id:
                        print(json.dumps({"request": payload["type"], "response": msg}, indent=2)[:2000])
                        break
                msg_id += 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
