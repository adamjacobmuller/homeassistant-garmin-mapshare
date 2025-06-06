"""Example integration using DataUpdateCoordinator."""

from datetime import timedelta
import logging

import async_timeout

from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, CONF_LINK_NAME, CONF_LINK_PASSWORD, WEB_BASE_URL
from .kml_fetch import KmlFetch

_LOGGER = logging.getLogger(__name__)


# async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
#     """Config entry example."""
#     # assuming API object stored here by __init__.py
#     my_api = hass.data[DOMAIN][entry.entry_id]
#     coordinator = MapShareCoordinator(hass, my_api)

#     # Fetch initial data so we have data when entities subscribe
#     #
#     # If the refresh fails, async_config_entry_first_refresh will
#     # raise ConfigEntryNotReady and setup will try again later
#     #
#     # If you do not want to retry setup on failure, use
#     # coordinator.async_refresh() instead
#     #
#     await coordinator.async_config_entry_first_refresh()

#     async_add_entities(
#         MapShareTrackerEntity(coordinator, idx) for idx, ent in enumerate(coordinator.data)
#     )


class MapShareCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize my coordinator."""
        _LOGGER.debug("MapShareCoordinator: %s", entry.data)

        self.mapshare = KmlFetch(
            hass, entry.data[CONF_LINK_NAME], entry.data.get(CONF_LINK_PASSWORD)
        )
        self.map_link_name: str = entry.data[CONF_LINK_NAME]
        self.raw_values: dict[str, dict[str, str]] = dict()

        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=f"{DOMAIN}-{entry.data[CONF_LINK_NAME]}",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(minutes=10),
        )

    async def _async_update_data(self) -> dict[str, str]:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                # Grab active context variables to limit data required to be fetched from API
                # Note: using context is not required if there is no need or ability to limit
                # data retrieved from API.
                self.raw_values = await self.mapshare.fetch_data()
                return self.raw_values
        # except ApiAuthError as err:
        #     # Raising ConfigEntryAuthFailed will cancel future updates
        #     # and start a config flow with SOURCE_REAUTH (async_step_reauth)
        #     raise ConfigEntryAuthFailed from err
        # except ApiError as err:
        #     raise UpdateFailed(f"Error communicating with API: {err}")
        finally:
            pass

    async def send_message(self, device_ids: list[str], message: str, from_addr: str = "HomeAssistant") -> None:
        """Send a message to InReach devices via MapShare."""
        from homeassistant.helpers.httpx_client import get_async_client
        
        # Convert IMEIs to device IDs if needed
        actual_device_ids = []
        for device_id in device_ids:
            if device_id in self.raw_values:
                # Extract the numeric ID from the device data
                device_data = self.raw_values[device_id]
                if "Id" in device_data:
                    actual_device_ids.append(str(device_data["Id"]))
                else:
                    _LOGGER.warning(f"No Id found for device {device_id}")
            else:
                # Assume it's already a device ID
                actual_device_ids.append(device_id)
        
        if not actual_device_ids:
            raise ValueError("No valid device IDs found")
        
        # Prepare the request
        url = f"{WEB_BASE_URL}{self.map_link_name}/Map/SendMessageToDevices"
        data = {
            "deviceIds": ",".join(actual_device_ids),
            "messageText": message,
            "fromAddr": from_addr
        }
        
        headers = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest",
            "origin": WEB_BASE_URL.rstrip("/"),
            "referer": f"{WEB_BASE_URL}{self.map_link_name}/"
        }
        
        # Note: This implementation may need additional authentication handling
        # The curl example shows cookies are required, which might need to be
        # obtained by first visiting the MapShare page
        client = get_async_client(self.hass)
        
        try:
            # First, try to get the MapShare page to obtain cookies
            page_response = await client.get(f"{WEB_BASE_URL}{self.map_link_name}/")
            
            # Then send the message
            response = await client.post(
                url,
                data=data,
                headers=headers,
                cookies=page_response.cookies
            )
            response.raise_for_status()
            
            _LOGGER.info(f"Successfully sent message to devices {actual_device_ids}")
        except Exception as e:
            _LOGGER.error(f"Failed to send message: {e}")
            raise UpdateFailed(f"Failed to send message: {e}") from e
