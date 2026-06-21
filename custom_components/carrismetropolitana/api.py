"""Carris Metropolitana API client."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://api.carrismetropolitana.pt/v2"

# Timeout configurável - aumentado para 30 segundos devido ao grande volume de dados
DEFAULT_TIMEOUT = 30


class CarrisMetropolitanaAPI:
    """API client for Carris Metropolitana."""

    def __init__(self, session: aiohttp.ClientSession, timeout: int = DEFAULT_TIMEOUT) -> None:
        """Initialize the API client."""
        self._session = session
        self._timeout = timeout
        _LOGGER.debug("API client initialized with timeout: %s seconds", timeout)

    async def _get(self, endpoint: str) -> Any:
        """Make a GET request to the API."""
        url = f"{BASE_URL}/{endpoint}"

        try:
            _LOGGER.debug("Carris API request: %s", url)

            async with self._session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as response:
                response.raise_for_status()

                data = await response.json(content_type=None)

                # Log apenas se for debug e tamanho controlado
                if _LOGGER.isEnabledFor(logging.DEBUG):
                    data_str = str(data)
                    if len(data_str) > 200:
                        data_str = f"{data_str[:200]}..."
                    _LOGGER.debug("Carris API response [%s]: %s", endpoint, data_str)

                return data

        except aiohttp.ClientResponseError as err:
            _LOGGER.error(
                "Carris API HTTP error %s for %s",
                err.status,
                url,
            )
            raise

        except aiohttp.ClientError as err:
            _LOGGER.error(
                "Carris API connection error for %s: %s",
                url,
                err,
            )
            raise

        except TimeoutError as err:
            _LOGGER.error(
                "Carris API timeout after %s seconds for %s: %s",
                self._timeout,
                url,
                err,
            )
            raise

        except Exception as err:
            _LOGGER.exception(
                "Unexpected error requesting %s: %s",
                url,
                err,
            )
            raise

    async def get_municipalities(self) -> list[dict]:
        """
        Extract municipalities from stops.

        NOTE:
        The API v2 currently does not document municipality_name,
        therefore extensive logging is enabled to verify available fields.
        """

        try:
            stops = await self._get("stops")

            if not isinstance(stops, list):
                _LOGGER.warning(
                    "Unexpected stops response type: %s",
                    type(stops),
                )
                return []

            if stops and _LOGGER.isEnabledFor(logging.DEBUG):
                # Log apenas uma amostra do primeiro stop
                sample = stops[0]
                sample_str = str(sample)
                if len(sample_str) > 200:
                    sample_str = f"{sample_str[:200]}..."
                _LOGGER.debug("Sample stop payload: %s", sample_str)

            seen: dict[str, str] = {}

            for stop in stops:
                municipality_id = stop.get("municipality_id")
                municipality_name = stop.get("municipality_name")

                locality_id = stop.get("locality_id")
                locality_name = stop.get("locality_name")

                entity_id = municipality_id or locality_id
                entity_name = municipality_name or locality_name

                if entity_id and entity_name:
                    seen[entity_id] = entity_name

            municipalities = [
                {"id": entity_id, "name": entity_name}
                for entity_id, entity_name in sorted(
                    seen.items(),
                    key=lambda item: item[1],
                )
            ]

            _LOGGER.info(
                "Loaded %s municipalities/localities",
                len(municipalities),
            )

            return municipalities

        except Exception as err:
            _LOGGER.exception(
                "Error fetching municipalities: %s",
                err,
            )
            return []

    async def get_lines(self) -> list[dict]:
        """Get all lines."""
        try:
            data = await self._get("lines")

            if not isinstance(data, list):
                _LOGGER.warning(
                    "Unexpected lines response type: %s",
                    type(data),
                )
                return []

            _LOGGER.info("Loaded %s lines", len(data))

            return data

        except Exception as err:
            _LOGGER.exception(
                "Error fetching lines: %s",
                err,
            )
            return []

    async def get_stops(self) -> list[dict]:
        """Get all stops."""
        try:
            data = await self._get("stops")

            if not isinstance(data, list):
                _LOGGER.warning(
                    "Unexpected stops response type: %s",
                    type(data),
                )
                return []

            _LOGGER.info("Loaded %s stops", len(data))

            return data

        except Exception as err:
            _LOGGER.exception(
                "Error fetching stops: %s",
                err,
            )
            return []

    async def get_arrivals_by_stop(self, stop_id: str) -> list[dict]:
        """Get arrivals for a specific stop."""
        try:
            data = await self._get(f"arrivals/by_stop/{stop_id}")

            if not isinstance(data, list):
                _LOGGER.warning(
                    "Unexpected arrivals response for stop %s: %s",
                    stop_id,
                    type(data),
                )
                return []

            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "Loaded %s arrivals for stop %s",
                    len(data),
                    stop_id,
                )

            return data

        except Exception as err:
            _LOGGER.warning(
                "Error fetching arrivals for stop %s: %s",
                stop_id,
                err,
            )
            return []

    async def get_vehicles(self) -> list[dict]:
        """Get all vehicle positions."""
        try:
            data = await self._get("vehicles")

            if not isinstance(data, list):
                _LOGGER.warning(
                    "Unexpected vehicles response type: %s",
                    type(data),
                )
                return []

            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "Loaded %s vehicles",
                    len(data),
                )

            return data

        except Exception as err:
            _LOGGER.exception(
                "Error fetching vehicles: %s",
                err,
            )
            return []

    async def get_alerts(self) -> list[dict]:
        """Get current service alerts."""
        try:
            data = await self._get("alerts")

            if isinstance(data, list):
                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug(
                        "Loaded %s alerts (list format)",
                        len(data),
                    )
                return data

            if isinstance(data, dict):
                entities = data.get("entity", [])

                if isinstance(entities, list):
                    if _LOGGER.isEnabledFor(logging.DEBUG):
                        _LOGGER.debug(
                            "Loaded %s alerts (GTFS entity format)",
                            len(entities),
                        )
                    return entities

            _LOGGER.warning(
                "Unexpected alerts payload format: %s",
                type(data),
            )

            return []

        except Exception as err:
            _LOGGER.warning(
                "Error fetching alerts: %s",
                err,
            )
            return []
