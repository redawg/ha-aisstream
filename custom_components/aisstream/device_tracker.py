from homeassistant.components.device_tracker import TrackerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_TRACK_AREA, DOMAIN
from .coordinator import AISstreamCoordinator
from .map_sync import MapDashboardSync


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AISstreamCoordinator = hass.data[DOMAIN][entry.entry_id]
    trackers: dict[str, AISVesselTracker] = {}
    track_area = entry.data.get(CONF_TRACK_AREA, False)
    map_sync = hass.data[DOMAIN].get("map_sync")
    if track_area and map_sync is None:
        map_sync = MapDashboardSync(hass)
        hass.data[DOMAIN]["map_sync"] = map_sync

    def add_tracker(mmsi: str) -> None:
        if mmsi in trackers:
            return
        tracker = AISVesselTracker(coordinator, mmsi, track_area=track_area, map_sync=map_sync)
        trackers[mmsi] = tracker
        async_add_entities([tracker])

    if track_area:
        coordinator.set_vessel_discovered_callback(add_tracker)
    else:
        for mmsi in coordinator.mmsi_list:
            add_tracker(mmsi)


class AISVesselTracker(TrackerEntity):
    """Device tracker entity for a single AIS vessel."""

    _attr_should_poll = False
    _attr_source_type = SourceType.GPS

    def __init__(
        self,
        coordinator: AISstreamCoordinator,
        mmsi: str,
        *,
        track_area: bool = False,
        map_sync: MapDashboardSync | None = None,
    ) -> None:
        self._coordinator = coordinator
        self._mmsi = mmsi
        self._track_area = track_area
        self._map_sync = map_sync
        self._attr_unique_id = f"aisstream_{mmsi}"
        self._remove_listener = None

    @property
    def _data(self) -> dict:
        return self._coordinator.vessel_data.get(self._mmsi, {})

    @property
    def name(self) -> str:
        return self._data.get("name") or f"Vessel {self._mmsi}"

    @property
    def latitude(self) -> float | None:
        return self._data.get("latitude")

    @property
    def longitude(self) -> float | None:
        return self._data.get("longitude")

    @property
    def extra_state_attributes(self) -> dict:
        exclude = {"latitude", "longitude", "name"}
        return {
            k: v
            for k, v in self._data.items()
            if k not in exclude and v is not None
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._mmsi)},
            name=self.name,
            manufacturer="AISstream",
            model=f"MMSI {self._mmsi}",
        )

    async def async_added_to_hass(self) -> None:
        self._remove_listener = self._coordinator.async_add_listener(
            self._mmsi, self.async_write_ha_state
        )
        if self._track_area and self._map_sync is not None:
            await self._map_sync.async_queue(self.entity_id, self.name)

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener:
            self._remove_listener()
