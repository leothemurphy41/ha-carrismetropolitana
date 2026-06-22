"""Config flow for Carris Metropolitana integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api import CarrisMetropolitanaAPI
from .const import CONF_LINE_IDS, CONF_MUNICIPALITY_IDS, CONF_STOP_IDS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class CarrisMetropolitanaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Carris Metropolitana."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._municipalities: dict[str, str] = {}
        self._lines: dict[str, str] = {}
        self._stops: dict[str, str] = {}
        self._selected_municipalities: list[str] = []
        self._selected_lines: list[str] = []
        self._stop_coords: dict[str, dict] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Select municipalities."""
        errors: dict[str, str] = {}

        _LOGGER.debug("Step user - user_input: %s", user_input)

        if not self._municipalities:
            session = async_get_clientsession(self.hass)
            api = CarrisMetropolitanaAPI(session)

            try:
                _LOGGER.debug("Fetching municipalities...")
                municipalities = await api.get_municipalities()
                _LOGGER.debug("Got %s municipalities", len(municipalities))

                self._municipalities = {}
                for m in municipalities:
                    mid = m.get("id")
                    name = m.get("name")
                    if mid and name:
                        self._municipalities[mid] = name

                if not self._municipalities:
                    _LOGGER.warning("No municipalities found")
                    errors["base"] = "cannot_connect"

            except Exception as err:
                _LOGGER.exception("Error fetching municipalities: %s", err)
                errors["base"] = "cannot_connect"

        if user_input is not None and not errors:
            self._selected_municipalities = user_input.get(CONF_MUNICIPALITY_IDS, [])
            _LOGGER.debug(
                "Selected %s municipalities: %s",
                len(self._selected_municipalities),
                self._selected_municipalities,
            )

            if not self._selected_municipalities:
                errors["base"] = "no_municipalities_selected"
            else:
                return await self.async_step_lines()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_MUNICIPALITY_IDS,
                    default=list(self._municipalities.keys()),
                ): cv.multi_select(
                    dict(
                        sorted(
                            self._municipalities.items(),
                            key=lambda x: x[1],
                        )
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_lines(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Select lines within chosen municipalities."""
        errors: dict[str, str] = {}

        _LOGGER.debug("Step lines - user_input: %s", user_input)

        if not self._lines:
            session = async_get_clientsession(self.hass)
            api = CarrisMetropolitanaAPI(session)

            try:
                _LOGGER.debug("Fetching all lines...")
                all_lines = await api.get_lines()
                _LOGGER.debug("Got %s total lines", len(all_lines))

                self._lines = {}
                for line in all_lines:
                    line_id = line.get("id")
                    if not line_id:
                        continue

                    mun_ids = line.get("municipality_ids", [])
                    if any(mid in self._selected_municipalities for mid in mun_ids):
                        short_name = line.get("short_name", line_id)
                        long_name = line.get("long_name", "")
                        label = f"{short_name} — {long_name}"[:80] if long_name else short_name
                        self._lines[line_id] = label
                        _LOGGER.debug("Added line: %s - %s", line_id, label)

                if not self._lines:
                    _LOGGER.warning("No lines found for selected municipalities")
                    errors["base"] = "no_lines_found"

            except Exception as err:
                _LOGGER.exception("Error fetching lines: %s", err)
                errors["base"] = "cannot_connect"

        if user_input is not None and not errors:
            self._selected_lines = user_input.get(CONF_LINE_IDS, [])
            _LOGGER.debug("Selected %s lines", len(self._selected_lines))
            return await self.async_step_stops()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LINE_IDS,
                    default=list(self._lines.keys())[:10],
                ): cv.multi_select(
                    dict(
                        sorted(
                            self._lines.items(),
                            key=lambda x: x[1],
                        )
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="lines",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_stops(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Select stops to monitor arrivals."""
        errors: dict[str, str] = {}

        _LOGGER.debug("Step stops - user_input: %s", user_input)

        if not self._stops:
            session = async_get_clientsession(self.hass)
            api = CarrisMetropolitanaAPI(session)

            try:
                _LOGGER.debug("Fetching all stops...")
                all_stops = await api.get_stops()
                _LOGGER.debug("Got %s total stops", len(all_stops))

                self._stops = {}
                self._stop_coords = {}

                for stop in all_stops:
                    stop_id = stop.get("id")
                    if not stop_id:
                        continue

                    mun_id = stop.get("municipality_id")
                    if mun_id in self._selected_municipalities:
                        name = (
                            stop.get("long_name")
                            or stop.get("name")
                            or stop.get("short_name")
                            or stop_id
                        )
                        self._stops[stop_id] = f"{name} ({stop_id})"

                        lat = stop.get("lat") or stop.get("latitude")
                        lon = stop.get("lon") or stop.get("longitude")
                        if lat is not None and lon is not None:
                            self._stop_coords[stop_id] = {"lat": lat, "lon": lon}

                        _LOGGER.debug("Added stop: %s - %s", stop_id, name)

                if not self._stops:
                    _LOGGER.warning(
                        "No stops found for selected municipalities. "
                        "User can continue without selecting stops."
                    )

            except Exception as err:
                _LOGGER.exception("Error fetching stops: %s", err)
                errors["base"] = "cannot_connect"

        if user_input is not None and not errors:
            selected_stops = user_input.get(CONF_STOP_IDS, [])
            _LOGGER.debug("Selected %s stops", len(selected_stops))

            municipality_names = [
                self._municipalities.get(mid, mid)
                for mid in self._selected_municipalities
            ]
            title = (
                f"Carris Metropolitana ({', '.join(municipality_names)})"
                if municipality_names
                else "Carris Metropolitana"
            )

            return self.async_create_entry(
                title=title,
                data={
                    CONF_MUNICIPALITY_IDS: self._selected_municipalities,
                    CONF_LINE_IDS: self._selected_lines,
                    CONF_STOP_IDS: selected_stops,
                    "stop_coords": self._stop_coords,
                },
            )

        if not self._stops:
            _LOGGER.info("No stops available. Allowing user to continue without stop selection.")
            return self.async_show_form(
                step_id="stops",
                data_schema=vol.Schema(
                    {
                        vol.Optional(CONF_STOP_IDS, default=[]): cv.multi_select({}),
                    }
                ),
                errors=errors,
                description_placeholders={
                    "warning": "⚠️ Nenhuma paragem encontrada para os municípios selecionados."
                },
            )

        schema = vol.Schema(
            {
                vol.Optional(CONF_STOP_IDS, default=[]): cv.multi_select(
                    dict(
                        sorted(
                            self._stops.items(),
                            key=lambda x: x[1],
                        )
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="stops",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "OptionsFlow":
        """Return the options flow."""
        return OptionsFlow()


class OptionsFlow(config_entries.OptionsFlow):
    """Options flow to update configuration."""

    def __init__(self) -> None:
        """Initialize options flow."""
        self._lines: dict[str, str] = {}
        self._stops: dict[str, str] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        _LOGGER.debug("Options step init - user_input: %s", user_input)

        # Aceder ao config_entry via self.config_entry (injectado pelo HA)
        selected_municipalities = list(
            self.config_entry.data.get(CONF_MUNICIPALITY_IDS, [])
        )

        if not self._lines:
            session = async_get_clientsession(self.hass)
            api = CarrisMetropolitanaAPI(session)

            try:
                _LOGGER.debug("Fetching lines for options...")
                all_lines = await api.get_lines()
                self._lines = {}

                for line in all_lines:
                    line_id = line.get("id")
                    if not line_id:
                        continue

                    mun_ids = line.get("municipality_ids", [])
                    if any(mid in selected_municipalities for mid in mun_ids):
                        short_name = line.get("short_name", line_id)
                        long_name = line.get("long_name", "")
                        label = f"{short_name} — {long_name}"[:80] if long_name else short_name
                        self._lines[line_id] = label

                _LOGGER.debug("Loaded %s lines for options", len(self._lines))

                _LOGGER.debug("Fetching stops for options...")
                all_stops = await api.get_stops()
                self._stops = {}

                for stop in all_stops:
                    stop_id = stop.get("id")
                    if not stop_id:
                        continue

                    if stop.get("municipality_id") in selected_municipalities:
                        name = (
                            stop.get("long_name")
                            or stop.get("name")
                            or stop.get("short_name")
                            or stop_id
                        )
                        self._stops[stop_id] = f"{name} ({stop_id})"

                _LOGGER.debug("Loaded %s stops for options", len(self._stops))

            except Exception as err:
                _LOGGER.exception("Error in options flow: %s", err)
                errors["base"] = "cannot_connect"

        if user_input is not None and not errors:
            new_lines = user_input.get(CONF_LINE_IDS, [])
            new_stops = user_input.get(CONF_STOP_IDS, [])

            _LOGGER.debug(
                "Saving options - Lines: %s, Stops: %s",
                len(new_lines),
                len(new_stops),
            )

            return self.async_create_entry(
                title="",
                data={
                    CONF_LINE_IDS: new_lines,
                    CONF_STOP_IDS: new_stops,
                },
            )

        current_lines = self.config_entry.options.get(
            CONF_LINE_IDS, self.config_entry.data.get(CONF_LINE_IDS, [])
        )
        current_stops = self.config_entry.options.get(
            CONF_STOP_IDS, self.config_entry.data.get(CONF_STOP_IDS, [])
        )

        schema = vol.Schema(
            {
                vol.Required(CONF_LINE_IDS, default=current_lines): cv.multi_select(
                    dict(sorted(self._lines.items(), key=lambda x: x[1]))
                ),
                vol.Optional(CONF_STOP_IDS, default=current_stops): cv.multi_select(
                    dict(sorted(self._stops.items(), key=lambda x: x[1]))
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
