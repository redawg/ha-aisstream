#!/usr/bin/env python3
"""Add AIS vessel trackers to the Map dashboard."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import aiohttp

HA_URL = os.environ.get("HA_URL", "http://172.16.255.250:8123").rstrip("/")
HA_WS = HA_URL.replace("http://", "ws://") + "/api/websocket"
MAP_URL_PATH = "map"
MCP_JSON = Path.home() / ".cursor" / "mcp.json"


def load_token() -> str:
    token = os.environ.get("HA_TOKEN", "").strip()
    if token:
        return token
    data = json.loads(MCP_JSON.read_text(encoding="utf-8"))
    return data["mcpServers"]["ha-forest"]["headers"]["Authorization"].split(" ", 1)[1].strip()


def get_vessel_entities(token: str) -> list[dict]:
    req = urllib.request.Request(
        f"{HA_URL}/api/states",
        headers={"Authorization": f"Bearer {token}"},
    )
    states = json.loads(urllib.request.urlopen(req, timeout=60).read())
    vessels = []
    for state in states:
        eid = state["entity_id"]
        if not eid.startswith("device_tracker.vessel_"):
            continue
        name = state.get("attributes", {}).get("friendly_name") or eid.split(".", 1)[1]
        vessels.append({
            "entity": eid,
            "name": name,
            "label_mode": "icon",
        })
    return sorted(vessels, key=lambda x: x["entity"])


async def get_map_config(token: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(HA_WS, timeout=60) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": token})
            await ws.receive_json()
            await ws.send_json({
                "id": 1,
                "type": "lovelace/config",
                "url_path": MAP_URL_PATH,
            })
            while True:
                msg = await ws.receive_json()
                if msg.get("id") == 1:
                    if not msg.get("success"):
                        raise RuntimeError(msg)
                    return msg["result"]


async def save_map_config(token: str, config: dict) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(HA_WS, timeout=60) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": token})
            await ws.receive_json()
            await ws.send_json({
                "id": 1,
                "type": "lovelace/config/save",
                "url_path": MAP_URL_PATH,
                "config": config,
            })
            while True:
                msg = await ws.receive_json()
                if msg.get("id") == 1:
                    return msg


def merge_vessels(config: dict, vessels: list[dict]) -> tuple[dict, int]:
    views = config.get("views", [])
    if not views:
        raise RuntimeError("Map dashboard has no views")

    card = views[0]["cards"][0]
    if card.get("type") != "map":
        raise RuntimeError("Expected first card to be map")

    existing = card.setdefault("entities", [])
    existing_entities = set()
    normalized = []

    for item in existing:
        if isinstance(item, str):
            existing_entities.add(item)
            normalized.append(item)
        elif isinstance(item, dict) and item.get("entity"):
            existing_entities.add(item["entity"])
            normalized.append(item)

    added = 0
    for vessel in vessels:
        if vessel["entity"] in existing_entities:
            continue
        normalized.append(vessel)
        existing_entities.add(vessel["entity"])
        added += 1

    card["entities"] = normalized
    return config, added


async def main() -> int:
    token = load_token()
    vessels = get_vessel_entities(token)
    print(f"found {len(vessels)} vessel trackers")

    config = await get_map_config(token)
    config, added = merge_vessels(config, vessels)
    print(f"adding {added} new entities to map dashboard")

    if added == 0:
        print("map dashboard already includes all vessel trackers")
        return 0

    result = await save_map_config(token, config)
    print("save:", result)
    if not result.get("success"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
