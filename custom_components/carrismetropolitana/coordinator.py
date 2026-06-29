"""DataUpdateCoordinator for Carris Metropolitana."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CarrisMetropolitanaAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=1)


class CarrisCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching Carris Metropolitana data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: CarrisMetropolitanaAPI,
        municipality_ids: list[str],
        line_ids: list[str],
        stop_ids: list[str],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        self.municipality_ids = municipality_ids or []
        self.line_ids = line_ids or []
        self.stop_ids = stop_ids or []

        _LOGGER.debug(
            "Coordinator initialized - Municipalities: %s, Lines: %s, Stops: %s",
            len(self.municipality_ids),
            len(self.line_ids),
            len(self.stop_ids),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the API in parallel."""
        _LOGGER.info("Starting Carris data update...")

        try:
            results = await asyncio.gather(
                self._fetch_all_arrivals(),
                self._fetch_vehicles(),
                self._fetch_alerts(),
                return_exceptions=True,
            )

            arrivals_result, vehicles_result, alerts_result = results

            data = {
                "arrivals": arrivals_result if not isinstance(arrivals_result, Exception) else {},
                "vehicles": vehicles_result if not isinstance(vehicles_result, Exception) else {},
                "alerts": alerts_result if not isinstance(alerts_result, Exception) else [],
            }

            if isinstance(arrivals_result, Exception):
                _LOGGER.error("Error fetching arrivals: %s", arrivals_result)
            if isinstance(vehicles_result, Exception):
                _LOGGER.error("Error fetching vehicles: %s", vehicles_result)
            if isinstance(alerts_result, Exception):
                _LOGGER.error("Error fetching alerts: %s", alerts_result)

            total_arrivals = sum(len(v) for v in data["arrivals"].values())
            total_vehicles = sum(len(v) for v in data["vehicles"].values())
            total_alerts = len(data["alerts"])

            _LOGGER.info(
                "Update complete - Arrivals: %s, Vehicles: %s, Alerts: %s",
                total_arrivals, total_vehicles, total_alerts,
            )

            return data

        except Exception as err:
            _LOGGER.exception("Unexpected error during data update: %s", err)
            raise UpdateFailed(
                f"Error communicating with Carris Metropolitana API: {err}"
            ) from err

    async def _fetch_all_arrivals(self) -> dict[str, list[dict]]:
        """Fetch arrivals for all stops in parallel."""
        if not self.stop_ids:
            return {}

        async def fetch_stop_arrivals(stop_id: str) -> tuple[str, list[dict]]:
            try:
                arrivals = await self.api.get_arrivals_by_stop(stop_id)
                return stop_id, arrivals if isinstance(arrivals, list) else []
            except Exception as err:
                _LOGGER.warning("Error fetching arrivals for stop %s: %s", stop_id, err)
                return stop_id, []

        tasks = [fetch_stop_arrivals(stop_id) for stop_id in self.stop_ids]
        results = await asyncio.gather(*tasks)

        arrivals_by_stop = {stop_id: arrivals for stop_id, arrivals in results}
        total = sum(len(v) for v in arrivals_by_stop.values())
        _LOGGER.debug("Fetched %s arrivals across %s stops", total, len(arrivals_by_stop))

        return arrivals_by_stop

    async def _fetch_vehicles(self) -> dict[str, list[dict]]:
        """Fetch vehicles and filter by configured lines."""
        if not self.line_ids:
            return {}

        try:
            all_vehicles = await self.api.get_vehicles()
            vehicles_by_line: dict[str, list[dict]] = {}
            line_ids_set = set(self.line_ids)

            for vehicle in all_vehicles:
                if not isinstance(vehicle, dict):
                    continue
                line_id = vehicle.get("line_id")
                if line_id in line_ids_set:
                    vehicles_by_line.setdefault(line_id, []).append(vehicle)

            total = sum(len(v) for v in vehicles_by_line.values())
            _LOGGER.debug("Filtered %s vehicles for %s lines", total, len(vehicles_by_line))

            return vehicles_by_line

        except Exception as err:
            _LOGGER.error("Error fetching vehicles: %s", err)
            return {}

    async def _fetch_alerts(self) -> list[dict]:
        """Fetch alerts."""
        try:
            alerts = await self.api.get_alerts()
            return alerts if isinstance(alerts, list) else []
        except Exception as err:
            _LOGGER.error("Error fetching alerts: %s", err)
            return []

    async def get_arrivals_for_stop(self, stop_id: str) -> list[dict]:
        """Get arrivals for a specific stop from cached data."""
        if not self.data:
            return []
        return self.data.get("arrivals", {}).get(stop_id, [])

    async def get_vehicles_for_line(self, line_id: str) -> list[dict]:
        """Get vehicles for a specific line from cached data."""
        if not self.data:
            return []
        return self.data.get("vehicles", {}).get(line_id, [])

    async def get_alerts(self) -> list[dict]:
        """Get alerts from cached data."""
        if not self.data:
            return []
        return self.data.get("alerts", [])

    async def is_stop_served(self, stop_id: str, line_id: str) -> bool:
        """Check if a stop is served by a specific line."""
        if not self.data:
            return False

        arrivals = self.data.get("arrivals", {}).get(stop_id, [])
        for arrival in arrivals:
            if arrival.get("line_id") == line_id:
                return True

        vehicles = self.data.get("vehicles", {}).get(line_id, [])
        for vehicle in vehicles:
            if vehicle.get("stop_id") == stop_id:
                return True

        return False
