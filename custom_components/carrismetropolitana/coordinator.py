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
TIMEOUT = 15  # seconds


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
        _LOGGER.info("🔄 Starting Carris data update...")

        try:
            tasks = {}
            
            # 1. Fetch arrivals for all stops (parallel)
            if self.stop_ids:
                tasks["arrivals"] = self._fetch_all_arrivals()
                _LOGGER.debug("Created arrivals task for %s stops", len(self.stop_ids))
            else:
                tasks["arrivals"] = asyncio.sleep(0, result={})
            
            # 2. Fetch vehicles
            if self.line_ids:
                tasks["vehicles"] = self._fetch_vehicles()
                _LOGGER.debug("Created vehicles task for %s lines", len(self.line_ids))
            else:
                tasks["vehicles"] = asyncio.sleep(0, result={})
            
            # 3. Fetch alerts
            tasks["alerts"] = self._fetch_alerts()
            _LOGGER.debug("Created alerts task")

            # Execute all tasks in parallel. Each API request already has its own timeout.
            _LOGGER.debug("Executing %s tasks", len(tasks))
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            _LOGGER.debug("All tasks completed, processing results")

            # Process results
            data = {}
            _LOGGER.debug("Processing %s results from tasks", len(results))
            for key, result in zip(tasks.keys(), results):
                if isinstance(result, Exception):
                    _LOGGER.error("Error fetching %s: %s", key, result)
                    data[key] = {} if key != "alerts" else []
                else:
                    data[key] = result
                    _LOGGER.debug("Successfully fetched %s: %s items", key, 
                                 len(result) if isinstance(result, dict) else len(result) if isinstance(result, list) else "unknown")

            # Log status
            try:
                total_arrivals = sum(len(v) for v in data.get("arrivals", {}).values())
            except Exception as e:
                _LOGGER.error("Error calculating arrivals count: %s", e)
                total_arrivals = 0
            
            try:
                total_vehicles = sum(len(v) for v in data.get("vehicles", {}).values())
            except Exception as e:
                _LOGGER.error("Error calculating vehicles count: %s", e)
                total_vehicles = 0
            
            try:
                total_alerts = len(data.get("alerts", []))
            except Exception as e:
                _LOGGER.error("Error calculating alerts count: %s", e)
                total_alerts = 0
            
            _LOGGER.info(
                "Update complete - Arrivals: %s, Vehicles: %s, Alerts: %s",
                total_arrivals,
                total_vehicles,
                total_alerts,
            )

            return data

        except asyncio.TimeoutError:
            _LOGGER.error("Data update timed out after %s seconds", TIMEOUT)
            raise UpdateFailed(f"Update timed out after {TIMEOUT} seconds")

        except Exception as err:
            _LOGGER.exception("Unexpected error during data update: %s", err)
            raise UpdateFailed(f"Error communicating with Carris Metropolitana API: {err}") from err

    async def _fetch_all_arrivals(self) -> dict[str, list[dict]]:
        """Fetch arrivals for all stops in parallel."""
        if not self.stop_ids:
            return {}

        _LOGGER.debug("Fetching arrivals for %s stops", len(self.stop_ids))

        async def fetch_stop_arrivals(stop_id: str) -> tuple[str, list[dict]]:
            try:
                _LOGGER.debug("Fetching arrivals for stop %s", stop_id)
                arrivals = await self.api.get_arrivals_by_stop(stop_id)
                _LOGGER.debug(
                    "Received %s arrivals for stop %s",
                    len(arrivals) if isinstance(arrivals, list) else 0,
                    stop_id,
                )
                return stop_id, arrivals if isinstance(arrivals, list) else []
            except Exception as err:
                _LOGGER.warning("Error fetching arrivals for stop %s: %s", stop_id, err)
                return stop_id, []

        # Execute all stop arrivals fetches in parallel
        tasks = [fetch_stop_arrivals(stop_id) for stop_id in self.stop_ids]
        results = await asyncio.gather(*tasks)

        arrivals_by_stop = {}
        for stop_id, arrivals in results:
            arrivals_by_stop[stop_id] = arrivals

        total = sum(len(v) for v in arrivals_by_stop.values())
        _LOGGER.debug("Fetched %s arrivals across %s stops", total, len(arrivals_by_stop))

        return arrivals_by_stop

    async def _fetch_vehicles(self) -> dict[str, list[dict]]:
        """Fetch vehicles and filter by configured lines."""
        if not self.line_ids:
            return {}

        try:
            all_vehicles = await self.api.get_vehicles()
            
            # Log apenas se houver veículos
            if all_vehicles and _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug("Got %s total vehicles", len(all_vehicles))

            vehicles_by_line = {}
            line_ids_set = set(self.line_ids)

            for vehicle in all_vehicles:
                if not isinstance(vehicle, dict):
                    continue

                line_id = vehicle.get("line_id")
                if line_id in line_ids_set:
                    vehicles_by_line.setdefault(line_id, []).append(vehicle)

            if _LOGGER.isEnabledFor(logging.DEBUG):
                total = sum(len(v) for v in vehicles_by_line.values())
                if total > 0:
                    _LOGGER.debug(
                        "Filtered %s vehicles for %s lines",
                        total,
                        len(vehicles_by_line),
                    )

            return vehicles_by_line

        except Exception as err:
            _LOGGER.error("Error fetching vehicles: %s", err)
            return {}

    async def _fetch_alerts(self) -> list[dict]:
        """Fetch alerts."""
        _LOGGER.debug("Fetching alerts")
        try:
            alerts = await self.api.get_alerts()
            count = len(alerts) if isinstance(alerts, list) else 0
            _LOGGER.debug("Received %s alerts", count)
            return alerts if isinstance(alerts, list) else []
        except Exception as err:
            _LOGGER.error("Error fetching alerts: %s", err)
            return []

    async def get_arrivals_for_stop(self, stop_id: str) -> list[dict]:
        """Get arrivals for a specific stop from cached data."""
        if not self.data:
            return []

        arrivals = self.data.get("arrivals", {}).get(stop_id, [])
        return arrivals

    async def get_vehicles_for_line(self, line_id: str) -> list[dict]:
        """Get vehicles for a specific line from cached data."""
        if not self.data:
            return []

        vehicles = self.data.get("vehicles", {}).get(line_id, [])
        return vehicles

    async def get_alerts(self) -> list[dict]:
        """Get alerts from cached data."""
        if not self.data:
            return []

        alerts = self.data.get("alerts", [])
        return alerts

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
