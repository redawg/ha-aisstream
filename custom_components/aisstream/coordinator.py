import asyncio
import json
import logging
import ssl
from collections.abc import Callable

import websockets
from homeassistant.core import HomeAssistant

from .const import AIS_URL, SEATTLE_AREA_BBOX

_LOGGER = logging.getLogger(__name__)

# AIS "not available" sentinel values
_LAT_UNAVAILABLE = 91.0
_LON_UNAVAILABLE = 181.0


class AISstreamCoordinator:
    """Manages the AISstream WebSocket connection and vessel data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        mmsi_list: list[str],
        *,
        track_area: bool = False,
    ) -> None:
        self.hass = hass
        self.api_key = api_key
        self.mmsi_list = mmsi_list
        self.track_area = track_area
        self.vessel_data: dict[str, dict] = {mmsi: {} for mmsi in mmsi_list}
        self._listeners: dict[str, list] = {mmsi: [] for mmsi in mmsi_list}
        self._task: asyncio.Task | None = None
        self._on_vessel_discovered: Callable[[str], None] | None = None
        self._discovered: set[str] = set(mmsi_list)

    def set_vessel_discovered_callback(self, callback: Callable[[str], None]) -> None:
        """Register callback for newly seen MMSIs in area mode."""
        self._on_vessel_discovered = callback

    def async_add_listener(self, mmsi: str, callback) -> callable:
        """Register a callback for updates to a specific MMSI. Returns a removal function."""
        self._listeners.setdefault(mmsi, []).append(callback)

        def remove():
            self._listeners[mmsi].remove(callback)

        return remove

    async def async_start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="aisstream_websocket")

    async def async_stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        retry_delay = 5
        while True:
            try:
                ssl_context = await self.hass.async_add_executor_job(
                    ssl.create_default_context
                )
                async with websockets.connect(AIS_URL, ssl=ssl_context) as ws:
                    await ws.send(self._build_subscribe_message())
                    _LOGGER.info(
                        "AISstream connected. track_area=%s MMSIs=%s",
                        self.track_area,
                        self.mmsi_list,
                    )
                    retry_delay = 5
                    async for message_json in ws:
                        self._process_message(message_json)
            except asyncio.CancelledError:
                return
            except Exception as err:
                _LOGGER.warning(
                    "AISstream disconnected: %s. Retrying in %ds", err, retry_delay
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 300)

    def _build_subscribe_message(self) -> str:
        payload: dict = {
            "APIKey": self.api_key,
            "BoundingBoxes": SEATTLE_AREA_BBOX if self.track_area else [[[-90, -180], [90, 180]]],
            "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
        }
        if self.mmsi_list and not self.track_area:
            payload["FiltersShipMMSI"] = self.mmsi_list
        return json.dumps(payload)

    def _process_message(self, message_json: str) -> None:
        try:
            msg = json.loads(message_json)
            msg_type = msg.get("MessageType")
            if msg_type == "PositionReport":
                self._handle_position_report(msg)
            elif msg_type == "ShipStaticData":
                self._handle_ship_static_data(msg)
        except Exception as err:
            _LOGGER.debug("Error processing AIS message: %s", err)

    def _ensure_vessel(self, mmsi: str) -> None:
        if mmsi in self._discovered:
            return
        self._discovered.add(mmsi)
        self.vessel_data.setdefault(mmsi, {})
        self._listeners.setdefault(mmsi, [])
        if self._on_vessel_discovered:
            self._on_vessel_discovered(mmsi)

    def _handle_position_report(self, msg: dict) -> None:
        r = msg["Message"]["PositionReport"]
        mmsi = str(r["UserID"])
        lat = r["Latitude"]
        lon = r["Longitude"]

        if lat == _LAT_UNAVAILABLE or lon == _LON_UNAVAILABLE:
            return

        if self.track_area or mmsi in self.mmsi_list:
            self._ensure_vessel(mmsi)

        if mmsi not in self.vessel_data:
            return

        self.vessel_data[mmsi].update({
            "latitude": lat,
            "longitude": lon,
            "sog": r.get("Sog"),
            "cog": r.get("Cog"),
            "true_heading": r.get("TrueHeading"),
            "navigational_status": r.get("NavigationalStatus"),
            "rate_of_turn": r.get("RateOfTurn"),
        })
        self._notify_listeners(mmsi)

    def _handle_ship_static_data(self, msg: dict) -> None:
        s = msg["Message"]["ShipStaticData"]
        mmsi = str(s["UserID"])

        if self.track_area or mmsi in self.mmsi_list:
            self._ensure_vessel(mmsi)

        if mmsi not in self.vessel_data:
            return

        self.vessel_data[mmsi].update({
            "name": s.get("Name", "").strip() or None,
            "call_sign": s.get("CallSign", "").strip() or None,
            "ship_type": s.get("Type"),
            "destination": s.get("Destination", "").strip() or None,
            "eta": s.get("Eta"),
            "draught": s.get("MaximumStaticDraught"),
            "imo": s.get("ImoNumber"),
        })
        self._notify_listeners(mmsi)

    def _notify_listeners(self, mmsi: str) -> None:
        for callback in self._listeners.get(mmsi, []):
            callback()
