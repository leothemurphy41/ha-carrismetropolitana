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
    """Set up vehicle device trackers for configured lines."""
    coordinator: CarrisCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Criar um tracker por linha em vez de por veículo
    # Isto evita o problema de entidades dinâmicas
    entities = []
    for line_id in coordinator.line_ids:
        entities.append(LineVehicleTracker(coordinator, line_id))
        _LOGGER.debug("Added vehicle tracker for line %s", line_id)

    if entities:
        async_add_entities(entities, update_before_add=True)


class LineVehicleTracker(CoordinatorEntity[CarrisCoordinator], TrackerEntity):
    """Tracker showing position of the first active vehicle on a line."""

    def __init__(self, coordinator: CarrisCoordinator, line_id: str) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator)
        self._line_id = line_id
        self._attr_name = f"Carris Veículo Linha {line_id}"
        self._attr_unique_id = f"{DOMAIN}_tracker_line_{line_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "carrismetropolitana")},
            name="Carris Metropolitana",
            manufacturer="Carris Metropolitana",
            model="API v2",
            configuration_url="https://www.carrismetropolitana.pt",
        )
        self._attr_icon = "mdi:bus"

    def _get_first_vehicle(self) -> dict | None:
        """Get the first active vehicle for this line."""
        if not self.coordinator.data:
            return None
        vehicles = self.coordinator.data.get("vehicles", {}).get(self._line_id, [])
        if vehicles and isinstance(vehicles, list):
            return vehicles[0]
        return None

    @property
    def latitude(self) -> float | None:
        """Return latitude."""
        vehicle = self._get_first_vehicle()
        if not vehicle:
            return None
        try:
            return float(vehicle.get("lat"))
        except (TypeError, ValueError):
            return None

    @property
    def longitude(self) -> float | None:
        """Return longitude."""
        vehicle = self._get_first_vehicle()
        if not vehicle:
            return None
        try:
            return float(vehicle.get("lon"))
        except (TypeError, ValueError):
            return None

    @property
    def source_type(self) -> SourceType:
        """Return source type."""
        return SourceType.GPS

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data is not None and self._get_first_vehicle() is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        vehicle = self._get_first_vehicle()
        if not vehicle:
            return {"line_id": self._line_id, "status": "Sem veículos"}

        attrs: dict[str, Any] = {
            "line_id": self._line_id,
            "vehicle_id": vehicle.get("id"),
            "speed": vehicle.get("speed"),
            "bearing": vehicle.get("bearing"),
            "current_stop": vehicle.get("stop_id"),
            "status": vehicle.get("current_status"),
        }

        if vehicle.get("license_plate"):
            attrs["license_plate"] = vehicle.get("license_plate")
        if vehicle.get("model"):
            attrs["model"] = vehicle.get("model")
        if vehicle.get("wheelchair_accessible") is not None:
            attrs["wheelchair_accessible"] = vehicle.get("wheelchair_accessible")

        return attrs
