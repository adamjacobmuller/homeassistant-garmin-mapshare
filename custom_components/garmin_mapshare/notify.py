"""Support for Garmin MapShare notifications."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.notify import (
    ATTR_TARGET,
    BaseNotificationService,
    NotifyEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .coordinator import MapShareCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Garmin MapShare notify platform."""
    # This is required for platforms to be loaded via config entries
    pass


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> MapShareNotificationService | None:
    """Get the Garmin MapShare notification service."""
    if discovery_info is None:
        return None

    coordinator: MapShareCoordinator = hass.data[DOMAIN][discovery_info["entry_id"]]
    return MapShareNotificationService(coordinator)


class MapShareNotificationService(BaseNotificationService):
    """Implementation of the Garmin MapShare notification service."""

    def __init__(self, coordinator: MapShareCoordinator) -> None:
        """Initialize the service."""
        self.coordinator = coordinator

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to Garmin InReach devices."""
        targets = kwargs.get(ATTR_TARGET)
        
        # Get all device IDs if no specific targets provided
        if not targets:
            device_ids = list(self.coordinator.data.keys())
        else:
            # Filter device IDs based on target device names or IMEIs
            device_ids = []
            for target in targets:
                for imei, device_data in self.coordinator.data.items():
                    if target in (imei, device_data.get("Name", ""), device_data.get("Map Display Name", "")):
                        device_ids.append(imei)
        
        if not device_ids:
            _LOGGER.warning("No valid device targets found for notification")
            return
        
        # Get from_addr from kwargs if provided
        from_addr = kwargs.get("data", {}).get("from_addr", "HomeAssistant")
        
        # Send the message using the coordinator
        try:
            await self.coordinator.send_message(device_ids, message, from_addr)
            _LOGGER.info(f"Sent message to devices {device_ids}: {message}")
        except Exception as e:
            _LOGGER.error(f"Failed to send message to devices: {e}")