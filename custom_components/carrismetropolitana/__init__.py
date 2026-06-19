"""Carris Metropolitana integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CarrisMetropolitanaAPI
from .const import (
    CONF_LINE_IDS,
    CONF_MUNICIPALITY_IDS,
    CONF_STOP_IDS,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import CarrisCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Carris Metropolitana from a config entry."""
    _LOGGER.debug("Setting up Carris Metropolitana entry: %s", entry.entry_id)

    try:
        # Initialize API client
        session = async_get_clientsession(hass)
        api = CarrisMetropolitanaAPI(session)

        # Get configuration from entry
        municipality_ids = list(
            entry.options.get(
                CONF_MUNICIPALITY_IDS,
                entry.data.get(CONF_MUNICIPALITY_IDS, []),
            )
        )
        line_ids = list(
            entry.options.get(
                CONF_LINE_IDS,
                entry.data.get(CONF_LINE_IDS, []),
            )
        )
        stop_ids = list(
            entry.options.get(
                CONF_STOP_IDS,
                entry.data.get(CONF_STOP_IDS, []),
            )
        )

        _LOGGER.debug(
            "Configuration loaded - Municipalities: %s, Lines: %s, Stops: %s",
            len(municipality_ids),
            len(line_ids),
            len(stop_ids),
        )

        # Initialize coordinator
        coordinator = CarrisCoordinator(
            hass=hass,
            api=api,
            municipality_ids=municipality_ids,
            line_ids=line_ids,
            stop_ids=stop_ids,
        )

        # Fetch initial data
        _LOGGER.debug("Fetching initial data from API...")
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.debug("Initial data fetch complete")

        # Store coordinator in hass data
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

        # Set up platforms
        _LOGGER.debug("Setting up platforms: %s", PLATFORMS)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        # Add update listener for options changes
        entry.async_on_unload(entry.add_update_listener(async_update_options))

        _LOGGER.info(
            "Carris Metropolitana integration setup complete for entry %s",
            entry.entry_id,
        )

        return True

    except Exception as err:
        _LOGGER.exception(
            "Failed to set up Carris Metropolitana integration: %s",
            err,
        )
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Carris Metropolitana entry: %s", entry.entry_id)

    try:
        # Unload platforms
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

        if unload_ok:
            # Remove coordinator from hass data
            hass.data[DOMAIN].pop(entry.entry_id, None)
            _LOGGER.debug("Successfully unloaded entry %s", entry.entry_id)
        else:
            _LOGGER.warning("Failed to unload platforms for entry %s", entry.entry_id)

        return unload_ok

    except Exception as err:
        _LOGGER.exception(
            "Error unloading Carris Metropolitana entry %s: %s",
            entry.entry_id,
            err,
        )
        return False


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update - reload the entry."""
    _LOGGER.debug("Options updated for entry %s, reloading...", entry.entry_id)

    try:
        await hass.config_entries.async_reload(entry.entry_id)
        _LOGGER.debug("Entry %s reloaded successfully", entry.entry_id)
    except Exception as err:
        _LOGGER.exception(
            "Error reloading entry %s after options update: %s",
            entry.entry_id,
            err,
        )


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of a config entry."""
    _LOGGER.debug("Removing Carris Metropolitana entry: %s", entry.entry_id)

    # Clean up any stored data
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.debug("Removed coordinator from hass data")

    _LOGGER.info(
        "Carris Metropolitana entry %s removed successfully",
        entry.entry_id,
    )
