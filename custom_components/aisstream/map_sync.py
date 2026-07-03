"""Keep the Map dashboard in sync with AIS vessel trackers."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

MAP_URL_PATH = "map"
LOVELACE_DATA = "lovelace"


class MapDashboardSync:
    """Debounced updater for vessel entities on the Map dashboard."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._pending: dict[str, str] = {}
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def async_queue(self, entity_id: str, name: str | None = None) -> None:
        """Queue a vessel entity to be added to the Map dashboard."""
        self._pending[entity_id] = name or entity_id
        if self._task is None or self._task.done():
            self._task = self._hass.async_create_task(self._debounced_flush())

    async def async_sync_all(self, entity_ids: list[str]) -> int:
        """Add any missing vessel entities to the Map dashboard immediately."""
        states = self._hass.states
        for entity_id in entity_ids:
            state = states.get(entity_id)
            name = state.name if state else entity_id
            self._pending[entity_id] = name
        return await self._flush()

    async def _debounced_flush(self) -> None:
        await asyncio.sleep(3)
        await self._flush()

    async def _flush(self) -> int:
        async with self._lock:
            if not self._pending:
                return 0
            pending = dict(self._pending)
            self._pending.clear()

        dashboard = self._get_map_dashboard()
        if dashboard is None:
            _LOGGER.debug("Map dashboard not found; skipping lovelace sync")
            return 0

        try:
            config = await dashboard.async_load(force=False)
        except Exception as err:
            _LOGGER.warning("Failed to load map dashboard: %s", err)
            return 0

        try:
            card, entities = _find_map_card(config)
        except ValueError as err:
            _LOGGER.warning("%s", err)
            return 0

        existing = _entity_ids_in_list(entities)
        added = 0
        for entity_id, name in sorted(pending.items()):
            if entity_id in existing:
                continue
            entities.append({
                "entity": entity_id,
                "name": name,
                "label_mode": "icon",
            })
            existing.add(entity_id)
            added += 1

        if added == 0:
            return 0

        try:
            await dashboard.async_save(config)
        except Exception as err:
            _LOGGER.warning("Failed to save map dashboard: %s", err)
            return 0

        _LOGGER.info("Added %d vessel(s) to Map dashboard", added)
        return added

    def _get_map_dashboard(self):
        lovelace = self._hass.data.get(LOVELACE_DATA)
        if lovelace is None:
            return None
        return lovelace.dashboards.get(MAP_URL_PATH)


def _find_map_card(config: dict[str, Any]) -> tuple[dict[str, Any], list]:
    views = config.get("views")
    if not views:
        raise ValueError("Map dashboard has no views")

    for view in views:
        for card in view.get("cards", []):
            if card.get("type") == "map":
                return card, card.setdefault("entities", [])

    raise ValueError("Map dashboard has no map card")


def _entity_ids_in_list(entities: list) -> set[str]:
    ids: set[str] = set()
    for item in entities:
        if isinstance(item, str):
            ids.add(item)
        elif isinstance(item, dict) and item.get("entity"):
            ids.add(item["entity"])
    return ids
