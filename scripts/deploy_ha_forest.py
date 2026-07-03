#!/usr/bin/env python3
"""Install ha-aisstream on Forest Home via HACS WebSocket API."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    import aiohttp
except ImportError:
    print("aiohttp is required: pip install aiohttp", file=sys.stderr)
    raise SystemExit(1)

HA_URL = os.environ.get("HA_URL", "http://172.16.255.250:8123").rstrip("/")
HA_WS = HA_URL.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
REPO_URL = os.environ.get("HACS_REPO_URL", "https://github.com/sh00t2kill/ha-aisstream")
REPO_NAME = os.environ.get("HACS_REPO", "sh00t2kill/ha-aisstream")
MCP_JSON = Path.home() / ".cursor" / "mcp.json"


def load_token() -> str:
    token = os.environ.get("HA_TOKEN", "").strip()
    if token:
        return token
    if MCP_JSON.is_file():
        data = json.loads(MCP_JSON.read_text(encoding="utf-8"))
        auth = data.get("mcpServers", {}).get("ha-forest", {}).get("headers", {}).get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth.split(" ", 1)[1].strip()
    print("Set HA_TOKEN or configure ha-forest in ~/.cursor/mcp.json", file=sys.stderr)
    raise SystemExit(1)


def rest_get(path: str, token: str) -> dict:
    req = urllib.request.Request(
        f"{HA_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def rest_post(path: str, token: str, payload: dict | None = None) -> tuple[int, str]:
    body = json.dumps(payload or {}).encode()
    req = urllib.request.Request(
        f"{HA_URL}{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


async def ws_call(ws: aiohttp.ClientWebSocketResponse, msg_id: int, payload: dict) -> dict:
    await ws.send_json({"id": msg_id, **payload})
    while True:
        msg = await ws.receive_json()
        if msg.get("id") == msg_id:
            return msg


async def hacs_install(token: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(HA_WS, timeout=60) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": token})
            auth = await ws.receive_json()
            if auth.get("type") != "auth_ok":
                raise RuntimeError(f"WebSocket auth failed: {auth}")

            add = await ws_call(
                ws,
                1,
                {
                    "type": "hacs/repositories/add",
                    "repository": REPO_URL,
                    "category": "integration",
                },
            )
            if add.get("success") is False and add.get("error"):
                print(f"hacs/repositories/add note: {add.get('error')}")

            listed = await ws_call(
                ws,
                2,
                {"type": "hacs/repositories/list", "categories": ["integration"]},
            )
            repos = listed.get("result", [])
            target = next((r for r in repos if r.get("full_name") == REPO_NAME), None)
            if not target:
                target = next(
                    (r for r in repos if "ha-aisstream" in str(r.get("full_name", "")).lower()),
                    None,
                )
            if not target:
                raise RuntimeError(f"HACS repo not found after add: {REPO_NAME}")

            repo_id = str(target["id"])
            print(f"Found HACS repo {target.get('full_name')} (id={repo_id})")

            download = await ws_call(
                ws,
                3,
                {"type": "hacs/repository/download", "repository": repo_id},
            )
            if download.get("success") is False:
                raise RuntimeError(f"HACS download failed: {download}")
            print("HACS download complete")
            return repo_id


def wait_for_ha(token: str, timeout_s: int = 180) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            rest_get("/api/", token)
            config = rest_get("/api/config", token)
            if config.get("state") == "RUNNING":
                print(f"HA running ({config.get('version')})")
                return
        except Exception:
            pass
        time.sleep(5)
    raise RuntimeError("Timed out waiting for Home Assistant to restart")


def main() -> int:
    token = load_token()
    print(f"Target: {HA_URL}")

    try:
        config = rest_get("/api/config", token)
        print(f"Connected to {config.get('location_name')} (HA {config.get('version')})")
    except Exception as exc:
        print(f"Cannot reach Home Assistant: {exc}", file=sys.stderr)
        return 1

    entries = rest_get("/api/config/config_entries/entry", token)
    existing = [e for e in entries if e.get("domain") == "aisstream"]
    if existing:
        print(f"aisstream already configured ({len(existing)} entries)")
        return 0

    try:
        repo_id = asyncio.run(hacs_install(token))
        print(f"Installed repository {repo_id}")
    except Exception as exc:
        print(f"HACS install failed: {exc}", file=sys.stderr)
        return 1

    status, body = rest_post("/api/services/homeassistant/restart", token)
    print(f"Restart requested: HTTP {status}")
    if status not in (200, 201):
        print(body)

    try:
        wait_for_ha(token)
    except Exception as exc:
        print(f"Warning: {exc}", file=sys.stderr)

    entries = rest_get("/api/config/config_entries/entry", token)
    if any(e.get("domain") == "aisstream" for e in entries):
        print("aisstream config entry found")
    else:
        print("Next: Settings -> Devices & Services -> Add Integration -> AISstream")
        print("You need an AISstream.io API key and vessel MMSI number(s).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
