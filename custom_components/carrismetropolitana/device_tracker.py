"""Device tracker platform for Carris Metropolitana vehicles."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up vehicle device trackers for configured lines."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Keep track of created trackers by vehicle id so we can add new ones dynamically
    trackers: dict[str, VehicleTracker] = {}

    vehicles_by_line = coordinator.data.get("vehicles", {}) if coordinator.data else {}

    initial_entities: list[TrackerEntity] = []

    for line_id, vehicles in vehicles_by_line.items():
        for vehicle in vehicles:
            vehicle_id = vehicle.get("id") or vehicle.get("vehicle_id")
            if not vehicle_id:
                continue
            vt = VehicleTracker(coordinator, str(vehicle_id), line_id)
            trackers[str(vehicle_id)] = vt
            initial_entities.append(vt)

    if initial_entities:
        async_add_entities(initial_entities)

    # Register a listener to add new trackers when new vehicles appear
    async def _handle_coordinator_update() -> None:
        vehicles_now = coordinator.data.get("vehicles", {}) if coordinator.data else {}
        found_ids: set[str] = set()

        # Add any new vehicles
        new_entities: list[TrackerEntity] = []
        for line_id, vehicles in vehicles_now.items():
            for vehicle in vehicles:
                vid = vehicle.get("id") or vehicle.get("vehicle_id")
                if not vid:
                    continue
                vid = str(vid)
                found_ids.add(vid)
                if vid not in trackers:
                    _LOGGER.debug("Adding new vehicle tracker for %s on line %s", vid, line_id)
                    vt = VehicleTracker(coordinator, vid, line_id)
                    trackers[vid] = vt
                    new_entities.append(vt)

        if new_entities:
            async_add_entities(new_entities)

        # Update existing trackers' state (will set to unavailable if vehicle missing)
        for vid, tracker in trackers.items():
            tracker._handle_coordinator_update()

    coordinator.async_add_listener(_handle_coordinator_update)


class VehicleTracker(CoordinatorEntity, TrackerEntity):
    """Tracker for a single vehicle."""

    def __init__(self, coordinator, vehicle_id: str, line_id: str) -> None:
        super().__init__(coordinator)
        self._vehicle_id = str(vehicle_id)
        self._line_id = line_id
        self._attr_name = f"Veículo {self._vehicle_id}"
        self._attr_unique_id = f"{DOMAIN}_vehicle_{self._vehicle_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"vehicle_{self._vehicle_id}")},
            name=f"Carris Veículo {self._vehicle_id}",
            manufacturer="Carris Metropolitana",
            model="Vehicle Tracker",
        )

        # Dynamic properties
        self._lat: float | None = None
        self._lon: float | None = None
        self._attrs: dict[str, Any] = {}

    @property
    def latitude(self) -> float | None:
        return self._lat

    @property
    def longitude(self) -> float | None:
        return self._lon

    @property
    def source_type(self) -> str:
        return "gps"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._attrs

    def _handle_coordinator_update(self) -> None:
        """Update tracker state from coordinator data."""
        vehicles = self.coordinator.data.get("vehicles", {}).get(self._line_id, []) if self.coordinator.data else []

        found = None
        for v in vehicles:
            vid = v.get("id") or v.get("vehicle_id")
            if str(vid) == self._vehicle_id:
                found = v
                break

        if found:
            try:
                lat = found.get("lat")
                lon = found.get("lon")
                self._lat = float(lat) if lat is not None else None
                self._lon = float(lon) if lon is not None else None
            except (TypeError, ValueError):
                self._lat = None
                self._lon = None

            # copy useful attributes
            self._attrs = {
                "line_id": found.get("line_id"),
                "speed": found.get("speed"),
                "bearing": found.get("bearing"),
                "current_stop": found.get("stop_id"),
            }

        else:
            # Vehicle no longer present
            self._lat = None
            self._lon = None
            self._attrs = {}

        self.async_write_ha_state()
