#!/usr/bin/env python3
"""List aisstream device trackers."""
import json
import urllib.request
from pathlib import Path

data = json.loads(Path.home().joinpath(".cursor/mcp.json").read_text())
token = data["mcpServers"]["ha-forest"]["headers"]["Authorization"].split(" ", 1)[1]
req = urllib.request.Request(
    "http://172.16.255.250:8123/api/states",
    headers={"Authorization": f"Bearer {token}"},
)
states = json.loads(urllib.request.urlopen(req, timeout=30).read())
trackers = sorted(
    s for s in states if s["entity_id"].startswith("device_tracker.") and "aisstream" in s["entity_id"]
)
print("aisstream trackers:", len(trackers))
for s in trackers[:25]:
    attrs = s.get("attributes", {})
    print(s["entity_id"], s.get("state"), attrs.get("friendly_name"), attrs.get("latitude"), attrs.get("longitude"))
