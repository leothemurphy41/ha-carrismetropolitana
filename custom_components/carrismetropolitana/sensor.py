"""Sensor platform for Carris Metropolitana."""
from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CarrisCoordinator

_LOGGER = logging.getLogger(__name__)

ARRIVALS_TO_SHOW = 5
MAX_ALERTS_TO_SHOW = 10


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Carris Metropolitana sensors."""
    coordinator: CarrisCoordinator = hass.data[DOMAIN][entry.entry_id]

    _LOGGER.debug(
        "Setting up sensors for entry %s - Stops: %s, Lines: %s",
        entry.entry_id,
        len(coordinator.stop_ids),
        len(coordinator.line_ids),
    )

    entities: list[SensorEntity] = []

    # Create stop sensors
    for stop_id in coordinator.stop_ids:
        entities.append(StopArrivalsSensor(coordinator, stop_id))
        _LOGGER.debug("Added stop sensor for %s", stop_id)

    # Create line sensors
    for line_id in coordinator.line_ids:
        entities.append(LineVehiclesSensor(coordinator, line_id))
        _LOGGER.debug("Added line sensor for %s", line_id)

    # Create alerts sensor
    entities.append(AlertsSensor(coordinator))
    _LOGGER.debug("Added alerts sensor")

    _LOGGER.info("Setting up %s Carris Metropolitana sensors", len(entities))
    async_add_entities(entities, update_before_add=True)

    # Add static/network sensors per municipality and per line
    static_entities: list[SensorEntity] = []

    # Lines per municipality
    for mun_id in coordinator.municipality_ids:
        static_entities.append(LinesMunicipalitySensor(coordinator, mun_id))

    # Stops per municipality
    for mun_id in coordinator.municipality_ids:
        static_entities.append(StopsMunicipalitySensor(coordinator, mun_id))

    # Line info sensors
    for line_id in coordinator.line_ids:
        static_entities.append(LineInfoSensor(coordinator, line_id))

    if static_entities:
        async_add_entities(static_entities, update_before_add=True)


class CarrisEntity(CoordinatorEntity[CarrisCoordinator], SensorEntity):
    """Base class for Carris Metropolitana entities."""

    def __init__(self, coordinator: CarrisCoordinator, unique_suffix: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "carrismetropolitana")},
            name="Carris Metropolitana",
            manufacturer="Carris Metropolitana",
            model="API v2",
            configuration_url="https://www.carrismetropolitana.pt",
        )
        _LOGGER.debug("Created CarrisEntity with unique_id: %s", self._attr_unique_id)

    @property
    def icon(self) -> str | None:
        """Return the entity icon."""
        return getattr(self, "_attr_icon", None)


class StopArrivalsSensor(CarrisEntity):
    """Sensor showing next arrivals at a stop."""

    def __init__(self, coordinator: CarrisCoordinator, stop_id: str) -> None:
        """Initialize the stop arrivals sensor."""
        super().__init__(coordinator, f"stop_{stop_id}")
        self._stop_id = stop_id
        self._attr_name = f"Carris Paragem {stop_id}"
        self._attr_icon = "mdi:bus-stop"

        _LOGGER.debug(
            "StopArrivalsSensor initialized for stop %s with unique_id: %s",
            stop_id,
            self._attr_unique_id,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data is not None

    @property
    def icon(self) -> str | None:
        """Return the entity icon."""
        return self._attr_icon

    @property
    def native_value(self) -> str | int | None:
        """Return the next arrival time or count."""
        try:
            if not self.coordinator.data:
                _LOGGER.debug("Stop %s: Coordinator data is None or empty", self._stop_id)
                return "A carregar..."

            arrivals = self._get_upcoming_arrivals()
            _LOGGER.debug("Stop %s: Found %s upcoming arrivals", self._stop_id, len(arrivals))
            
            if not arrivals:
                return "Sem serviço"

            first_arrival = arrivals[0]
            estimated = first_arrival.get("estimated_arrival")
            scheduled = first_arrival.get("scheduled_arrival")
            observed = first_arrival.get("observed_arrival")

            # Prefer observed > estimated > scheduled
            value = observed or estimated or scheduled
            
            if value:
                return value
            
            # Se não houver horário, mostra o número de chegadas
            result = f"{len(arrivals)} chegadas"
            _LOGGER.debug("Stop %s: Returning fallback value: %s", self._stop_id, result)
            return result
        except Exception as err:
            _LOGGER.exception("Error calculating native_value for stop %s: %s", self._stop_id, err)
            return "Erro"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes with next arrivals."""
        if not self.coordinator.data:
            return {
                "stop_id": self._stop_id,
                "status": "A carregar dados...",
                "next_arrivals": [],
            }

        arrivals = self._get_upcoming_arrivals()

        attrs: dict[str, Any] = {
            "stop_id": self._stop_id,
            "total_arrivals": len(arrivals),
            "next_arrivals": [],
        }

        # Add up to ARRIVALS_TO_SHOW arrivals
        for idx, arrival in enumerate(arrivals[:ARRIVALS_TO_SHOW], 1):
            arrival_data = {
                "position": idx,
                "line": arrival.get("line_id"),
                "headsign": arrival.get("headsign"),
                "trip_id": arrival.get("trip_id"),
                "vehicle_id": arrival.get("vehicle_id"),
            }

            # Add time information
            estimated = arrival.get("estimated_arrival")
            scheduled = arrival.get("scheduled_arrival")
            observed = arrival.get("observed_arrival")

            if estimated:
                arrival_data["estimated_arrival"] = estimated
            if scheduled:
                arrival_data["scheduled_arrival"] = scheduled
            if observed:
                arrival_data["observed_arrival"] = observed

            # Add delay if available
            delay = arrival.get("delay")
            if delay is not None:
                arrival_data["delay_seconds"] = delay

            attrs["next_arrivals"].append(arrival_data)

        # Set first arrival as main attributes for easy access
        if arrivals:
            first = arrivals[0]
            attrs["line"] = first.get("line_id")
            attrs["headsign"] = first.get("headsign")
            attrs["estimated_arrival"] = first.get("estimated_arrival")
            attrs["scheduled_arrival"] = first.get("scheduled_arrival")

            delay = first.get("delay")
            if delay is not None:
                attrs["delay_seconds"] = delay
        else:
            attrs["status"] = "Sem serviço"

        return attrs

    def _get_upcoming_arrivals(self) -> list[dict]:
        """Get arrivals that haven't happened yet, sorted by time."""
        if not self.coordinator.data:
            return []

        all_arrivals = self.coordinator.data.get("arrivals", {}).get(
            self._stop_id, []
        )

        if not all_arrivals:
            _LOGGER.debug("Stop %s: No arrivals data available", self._stop_id)
            return []

        now_unix = int(time.time())
        upcoming = []

        for arrival in all_arrivals:
            if not isinstance(arrival, dict):
                continue

            # Try to get UNIX timestamps
            estimated_unix = arrival.get("estimated_arrival_unix")
            scheduled_unix = arrival.get("scheduled_arrival_unix")
            observed_unix = arrival.get("observed_arrival_unix")

            # Use the most reliable timestamp available
            unix = observed_unix or estimated_unix or scheduled_unix

            if unix is not None:
                try:
                    if int(unix) >= now_unix:
                        upcoming.append(arrival)
                    else:
                        _LOGGER.debug(
                            "Skipping past arrival for stop %s: %s (now: %s)",
                            self._stop_id,
                            unix,
                            now_unix,
                        )
                except (ValueError, TypeError):
                    # Fallback: try with string comparison
                    scheduled = arrival.get("scheduled_arrival", "")
                    estimated = arrival.get("estimated_arrival", "")
                    compare_time = estimated or scheduled

                    if compare_time:
                        current_time = time.strftime("%H:%M:%S")
                        if compare_time >= current_time:
                            upcoming.append(arrival)
            else:
                # Fallback: use string time comparison
                scheduled = arrival.get("scheduled_arrival", "")
                estimated = arrival.get("estimated_arrival", "")
                compare_time = estimated or scheduled

                if compare_time:
                    current_time = time.strftime("%H:%M:%S")
                    if compare_time >= current_time:
                        upcoming.append(arrival)

        # Sort by time (prefer UNIX timestamps)
        def sort_key(arrival: dict) -> str:
            """Sort key for arrivals."""
            # Try UNIX timestamps first
            unix = (
                arrival.get("observed_arrival_unix")
                or arrival.get("estimated_arrival_unix")
                or arrival.get("scheduled_arrival_unix")
            )
            if unix is not None:
                return str(unix)

            # Fallback to string comparison
            return (
                arrival.get("estimated_arrival")
                or arrival.get("scheduled_arrival")
                or ""
            )

        upcoming.sort(key=sort_key)

        _LOGGER.debug(
            "Stop %s: %s upcoming arrivals out of %s total",
            self._stop_id,
            len(upcoming),
            len(all_arrivals),
        )

        return upcoming


class LineVehiclesSensor(CarrisEntity):
    """Sensor showing number of active vehicles on a line."""

    def __init__(self, coordinator: CarrisCoordinator, line_id: str) -> None:
        """Initialize the line vehicles sensor."""
        super().__init__(coordinator, f"line_{line_id}")
        self._line_id = line_id
        self._attr_name = f"Carris Linha {line_id}"
        self._attr_icon = "mdi:bus"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "veículos"

        _LOGGER.debug(
            "LineVehiclesSensor initialized for line %s with unique_id: %s",
            line_id,
            self._attr_unique_id,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data is not None

    @property
    def icon(self) -> str | None:
        """Return the entity icon."""
        return self._attr_icon

    @property
    def native_value(self) -> int:
        """Return number of active vehicles on the line."""
        try:
            if not self.coordinator.data:
                _LOGGER.debug("Line %s: Coordinator data is None or empty", self._line_id)
                return 0

            vehicles_data = self.coordinator.data.get("vehicles", {})
            vehicles = vehicles_data.get(self._line_id, [])
            count = len(vehicles) if isinstance(vehicles, list) else 0

            _LOGGER.debug("Line %s: Found %s vehicles", self._line_id, count)
            return count
        except Exception as err:
            _LOGGER.exception("Error calculating native_value for line %s: %s", self._line_id, err)
            return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return vehicle details."""
        if not self.coordinator.data:
            return {
                "line_id": self._line_id,
                "status": "A carregar dados...",
                "vehicles": [],
            }

        vehicles = self.coordinator.data.get("vehicles", {}).get(self._line_id, [])

        if not isinstance(vehicles, list):
            vehicles = []

        vehicle_details = []
        for v in vehicles:
            if not isinstance(v, dict):
                continue

            detail = {
                "id": v.get("id"),
                "lat": v.get("lat"),
                "lon": v.get("lon"),
            }

            # Add optional fields if available
            if v.get("speed") is not None:
                detail["speed"] = v.get("speed")
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
            if v.get("wheelchair_accessible") is not None:
                detail["wheelchair_accessible"] = v.get("wheelchair_accessible")
            if v.get("timestamp"):
                detail["timestamp"] = v.get("timestamp")

            vehicle_details.append(detail)

        return {
            "line_id": self._line_id,
            "total_vehicles": len(vehicle_details),
            "vehicles": vehicle_details,
        }


class LinesMunicipalitySensor(CarrisEntity, SensorEntity):
    """Sensor that lists lines serving a municipality."""

    def __init__(self, coordinator: CarrisCoordinator, municipality_id: str) -> None:
        super().__init__(coordinator, f"lines_mun_{municipality_id}")
        self._municipality_id = municipality_id
        self._attr_name = f"Linhas Município {municipality_id}"
        self._lines: list[dict] = []

    @property
    def native_value(self) -> int:
        return len(self._lines)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"lines": self._lines}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._fetch()

    async def _fetch(self) -> None:
        try:
            lines = await self.coordinator.api.get_lines()
            # Attempt to filter by municipality_id if present on line
            filtered = [l for l in lines if l.get("municipality_id") == self._municipality_id]
            if not filtered:
                # fallback: include lines that reference municipality in name
                filtered = [l for l in lines if self._municipality_id in (l.get("name") or "")]
            self._lines = filtered
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.debug("Error fetching lines for municipality %s: %s", self._municipality_id, err)


class StopsMunicipalitySensor(CarrisEntity, SensorEntity):
    """Sensor that lists stops in a municipality."""

    def __init__(self, coordinator: CarrisCoordinator, municipality_id: str) -> None:
        super().__init__(coordinator, f"stops_mun_{municipality_id}")
        self._municipality_id = municipality_id
        self._attr_name = f"Paragens Município {municipality_id}"
        self._stops: list[dict] = []

    @property
    def native_value(self) -> int:
        return len(self._stops)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"stops": self._stops}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._fetch()

    async def _fetch(self) -> None:
        try:
            stops = await self.coordinator.api.get_stops()
            filtered = [s for s in stops if s.get("municipality_id") == self._municipality_id]
            self._stops = filtered
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.debug("Error fetching stops for municipality %s: %s", self._municipality_id, err)


class LineInfoSensor(CarrisEntity, SensorEntity):
    """Sensor that exposes static info about a line."""

    def __init__(self, coordinator: CarrisCoordinator, line_id: str) -> None:
        super().__init__(coordinator, f"line_info_{line_id}")
        self._line_id = line_id
        self._attr_name = f"Informação Linha {line_id}"
        self._info: dict[str, Any] = {}

    @property
    def native_value(self) -> str:
        return self._info.get("name", "Desconhecido")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._info

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._fetch()

    async def _fetch(self) -> None:
        try:
            lines = await self.coordinator.api.get_lines()
            found = next((l for l in lines if str(l.get("id")) == str(self._line_id)), None)
            if found:
                self._info = found
            else:
                self._info = {}
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.debug("Error fetching info for line %s: %s", self._line_id, err)


class AlertsSensor(CarrisEntity):
    """Sensor showing active service alerts."""

    def __init__(self, coordinator: CarrisCoordinator) -> None:
        """Initialize the alerts sensor."""
        super().__init__(coordinator, f"alerts_{id(coordinator)}")
        self._attr_name = "Carris Alertas"
        self._attr_icon = "mdi:alert-circle"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "alertas"
        self._attr_entity_registry_enabled_default = False

        _LOGGER.debug("AlertsSensor initialized with unique_id: %s", self._attr_unique_id)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data is not None

    @property
    def icon(self) -> str | None:
        """Return the entity icon."""
        return self._attr_icon

    @property
    def native_value(self) -> int:
        """Return number of active alerts."""
        try:
            if not self.coordinator.data:
                _LOGGER.debug("Alerts: Coordinator data is None or empty")
                return 0

            alerts = self.coordinator.data.get("alerts", [])
            count = len(alerts) if isinstance(alerts, list) else 0

            _LOGGER.debug("Alerts: Found %s alerts", count)
            return count
        except Exception as err:
            _LOGGER.exception("Error calculating native_value for alerts: %s", err)
            return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return alert details."""
        if not self.coordinator.data:
            return {
                "status": "A carregar dados...",
                "alerts": [],
            }

        alerts = self.coordinator.data.get("alerts", [])

        if not isinstance(alerts, list):
            return {"alerts": []}

        alert_summaries = []
        for alert in alerts[:MAX_ALERTS_TO_SHOW]:
            if not isinstance(alert, dict):
                continue

            # Try to extract alert data
            alert_data = alert.get("alert", alert)

            # Extract header text
            header_text = alert_data.get("header_text")
            if isinstance(header_text, dict):
                translations = header_text.get("translation", [])
                if isinstance(translations, list):
                    # Find Portuguese translation
                    pt_text = next(
                        (
                            t.get("text", "")
                            for t in translations
                            if isinstance(t, dict) and t.get("language") == "pt"
                        ),
                        "",
                    )
                    # Fallback to first translation
                    if not pt_text and translations:
                        pt_text = translations[0].get("text", "")
                    header = str(pt_text) if pt_text else ""
                else:
                    header = str(header_text)
            else:
                header = str(header_text) if header_text is not None else ""

            # Extract description
            description_text = alert_data.get("description_text")
            if isinstance(description_text, dict):
                translations = description_text.get("translation", [])
                if isinstance(translations, list):
                    pt_text = next(
                        (
                            t.get("text", "")
                            for t in translations
                            if isinstance(t, dict) and t.get("language") == "pt"
                        ),
                        "",
                    )
                    if not pt_text and translations:
                        pt_text = translations[0].get("text", "")
                    description = str(pt_text) if pt_text else ""
                else:
                    description = str(description_text)
            else:
                description = str(description_text) if description_text is not None else ""

            # Build summary
            summary = {}
            if header:
                summary["header"] = header
            if description:
                summary["description"] = description

            if summary:
                alert_summaries.append(summary)

        return {
            "total_alerts": len(alert_summaries),
            "alerts": alert_summaries,
        }
