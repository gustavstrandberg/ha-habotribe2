"""Data coordinator for HABO Tribe2 Smart Lock."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthenticationError, HaboTribe2Client, HaboTribe2Error, LockState
from .const import (
    CONF_DEVICE_ID,
    CONF_GATEWAY_ID,
    CONF_LOCK_ADDR,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class HaboTribe2Coordinator(DataUpdateCoordinator[LockState]):
    """Coordinate polling of one HABO Tribe2 lock."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: HaboTribe2Client,
    ) -> None:
        self.entry = entry
        self.client = client
        self.device_id = entry.data[CONF_DEVICE_ID]
        self.gateway_id = entry.data[CONF_GATEWAY_ID]
        self.lock_addr = entry.data[CONF_LOCK_ADDR]
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS),
        )

    async def _async_update_data(self) -> LockState:
        try:
            return await self.client.async_get_lock(self.device_id)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("HABO authentication failed") from err
        except HaboTribe2Error as err:
            raise UpdateFailed(str(err)) from err
