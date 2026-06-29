"""Device tracker platform for Carris Metropolitana vehicles."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CarrisCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up vehicle device trackers — one per configured line."""
    coordinator: CarrisCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for line_id in coordinator.line_ids:
        entities.append(LineVehicleTracker(coordinator, line_id))
        _LOGGER.debug("Added tracker for line %s", line_id)

    if entities:
        async_add_entities(entities, update_before_add=True)


class LineVehicleTracker(CoordinatorEntity[CarrisCoordinator], TrackerEntity):
    """Tracker showing the first active vehicle on a line.
    
    One tracker per line — never becomes a ghost entity.
    """

    def __init__(self, coordinator: CarrisCoordinator, line_id: str) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator)
        self._line_id = line_id
        self._attr_name = f"Carris Linha {line_id} — Veículo"
        self._attr_unique_id = f"{DOMAIN}_tracker_line_{line_id}"
        self._attr_icon = "mdi:bus"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "carrismetropolitana")},
            name="Carris Metropolitana",
            manufacturer="Carris Metropolitana",
            model="API v2",
            configuration_url="https://www.carrismetropolitana.pt",
        )

    def _get_vehicles(self) -> list[dict]:
        """Get all active vehicles for this line."""
        if not self.coordinator.data:
            return []
        return self.coordinator.data.get("vehicles", {}).get(self._line_id, [])

    def _get_first_vehicle(self) -> dict | None:
        """Get the first active vehicle for this line."""
        vehicles = self._get_vehicles()
        return vehicles[0] if vehicles else None

    @property
    def available(self) -> bool:
        """Available when coordinator has data — even if no vehicles."""
        return self.coordinator.data is not None

    @property
    def latitude(self) -> float | None:
        """Return latitude of first vehicle."""
        v = self._get_first_vehicle()
        if not v:
            return None
        try:
            return float(v.get("lat"))
        except (TypeError, ValueError):
            return None

    @property
    def longitude(self) -> float | None:
        """Return longitude of first vehicle."""
        v = self._get_first_vehicle()
        if not v:
            return None
        try:
            return float(v.get("lon"))
        except (TypeError, ValueError):
            return None

    @property
    def source_type(self) -> SourceType:
        """Return source type."""
        return SourceType.GPS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return all active vehicles as attributes."""
        vehicles = self._get_vehicles()
        if not vehicles:
            return {
                "line_id": self._line_id,
                "active_vehicles": 0,
                "vehicles": [],
            }

        vehicle_list = []
        for v in vehicles:
            detail: dict[str, Any] = {
                "id": v.get("id"),
                "lat": v.get("lat"),
                "lon": v.get("lon"),
            }
            if v.get("speed") is not None:
                detail["speed"] = round(v.get("speed"), 1)
            if v.get("bearing") is not None:
                detail["bearing"] = v.get("bearing")
            if v.get("stop_id"):
                detail["current_stop"] = v.get("stop_id")
            if v.get("current_status"):
                detail["status"] = v.get("current_status")
            if v.get("license_plate"):
                detail["license_plate"] = v.get("license_plate")
            if v.get("model"):
                detail["model"] = v.get("model")
            vehicle_list.append(detail)

        first = vehicles[0]
        return {
            "line_id": self._line_id,
            "active_vehicles": len(vehicles),
            "vehicle_id": first.get("id"),
            "speed": round(first.get("speed", 0), 1),
            "bearing": first.get("bearing"),
            "current_stop": first.get("stop_id"),
            "status": first.get("current_status"),
            "license_plate": first.get("license_plate"),
            "vehicles": vehicle_list,
        }
