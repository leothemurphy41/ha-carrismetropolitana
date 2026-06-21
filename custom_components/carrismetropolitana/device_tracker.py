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

    # ⚠️ ALTERAÇÃO CRÍTICA: Usar async_add_entities com update_before_add
    # e remover chamada direta a _handle_coordinator_update
    async def _handle_coordinator_update() -> None:
        """Handle coordinator updates - add new vehicles and update existing ones."""
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
            # Adicionar novas entidades com update_before_add=True
            async_add_entities(new_entities, update_before_add=True)

        # ⚠️ ALTERAÇÃO CRÍTICA: Não chamar _handle_coordinator_update() diretamente
        # Em vez disso, forçar a atualização do estado das entidades existentes
        for vid, tracker in trackers.items():
            # Verificar se o veículo ainda existe nos dados
            vehicle_exists = False
            for line_id, vehicles in vehicles_now.items():
                for vehicle in vehicles:
                    v_id = vehicle.get("id") or vehicle.get("vehicle_id")
                    if str(v_id) == vid:
                        vehicle_exists = True
                        break
                if vehicle_exists:
                    break
            
            if vehicle_exists:
                # Forçar atualização do tracker via CoordinatorEntity
                tracker.async_update_ha_state()
            else:
                # Marcar como unavailable
                tracker._update_from_data(None)
                tracker.async_write_ha_state()

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
        
        # ⚠️ ALTERAÇÃO: Inicializar com dados atuais
        self._update_from_data(self._find_vehicle_data())

    def _find_vehicle_data(self) -> dict | None:
        """Find vehicle data in coordinator."""
        if not self.coordinator.data:
            return None
        
        vehicles = self.coordinator.data.get("vehicles", {}).get(self._line_id, [])
        for v in vehicles:
            vid = v.get("id") or v.get("vehicle_id")
            if str(vid) == self._vehicle_id:
                return v
        return None

    def _update_from_data(self, vehicle_data: dict | None) -> None:
        """Update tracker state from vehicle data."""
        if vehicle_data:
            try:
                lat = vehicle_data.get("lat")
                lon = vehicle_data.get("lon")
                self._lat = float(lat) if lat is not None else None
                self._lon = float(lon) if lon is not None else None
            except (TypeError, ValueError):
                self._lat = None
                self._lon = None

            # Copy useful attributes
            self._attrs = {
                "line_id": vehicle_data.get("line_id"),
                "speed": vehicle_data.get("speed"),
                "bearing": vehicle_data.get("bearing"),
                "current_stop": vehicle_data.get("stop_id"),
                "vehicle_id": self._vehicle_id,
            }
            
            # Adicionar atributos opcionais se existirem
            if vehicle_data.get("license_plate"):
                self._attrs["license_plate"] = vehicle_data.get("license_plate")
            if vehicle_data.get("model"):
                self._attrs["model"] = vehicle_data.get("model")
            if vehicle_data.get("wheelchair_accessible") is not None:
                self._attrs["wheelchair_accessible"] = vehicle_data.get("wheelchair_accessible")
            if vehicle_data.get("timestamp"):
                self._attrs["timestamp"] = vehicle_data.get("timestamp")
        else:
            # Vehicle no longer present - marcar como unavailable
            self._lat = None
            self._lon = None
            self._attrs = {"status": "unavailable", "vehicle_id": self._vehicle_id}

    @property
    def latitude(self) -> float | None:
        """Return latitude for tracking."""
        return self._lat

    @property
    def longitude(self) -> float | None:
        """Return longitude for tracking."""
        return self._lon

    @property
    def source_type(self) -> str:
        """Return source type for tracking."""
        return "gps"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        return self._attrs

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Está disponível se tiver coordenadas válidas
        return self._lat is not None and self._lon is not None

    def _handle_coordinator_update(self) -> None:
        """⚠️ ALTERAÇÃO CRÍTICA: Sobrescrever método corretamente."""
        """Update tracker state from coordinator data."""
        _LOGGER.debug(
            "Updating vehicle tracker %s from coordinator",
            self._vehicle_id
        )
        
        # Encontrar dados do veículo
        vehicle_data = self._find_vehicle_data()
        
        # Atualizar estado
        self._update_from_data(vehicle_data)
        
        # Notificar HA da mudança
        self.async_write_ha_state()
