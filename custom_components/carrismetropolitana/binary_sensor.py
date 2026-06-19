"""Binary sensor platform for Carris Metropolitana alerts."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEFAULT_ALERT_ICON

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up binary sensors for the entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BinarySensorEntity] = [AlertsBinarySensor(coordinator)]

    async_add_entities(entities)


class AlertsBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor that indicates whether there are active alerts."""

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = "Carris Alertas Ativas"
        self._attr_unique_id = f"{DOMAIN}_alerts"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "carrismetropolitana")},
            name="Carris Metropolitana",
            manufacturer="Carris Metropolitana",
            model="API v2",
        )
        self._attr_icon = DEFAULT_ALERT_ICON

    @property
    def is_on(self) -> bool:
        """Return True if there are active alerts."""
        alerts = self.coordinator.data.get("alerts", []) if self.coordinator.data else []
        return bool(alerts)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return alert details as attributes."""
        if not self.coordinator.data:
            return {"alerts": []}

        return {"alerts": self.coordinator.data.get("alerts", [])}
