"""Lock platform for HABO Tribe2 Smart Lock."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import AuthenticationError, HaboTribe2Error, LockBusyError
from .const import (
    ATTR_BATTERY_LEVEL,
    ATTR_CONNECTED,
    ATTR_DOOR_OPEN,
    ATTR_LAST_SEEN,
    ATTR_LOCK_ADDR,
    ATTR_OPERATING_MODE,
    ATTR_VOLTAGE_MV,
    DOMAIN,
)
from .coordinator import HaboTribe2Coordinator
from .entity import HaboTribe2Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HABO Tribe2 lock entity."""

    async_add_entities([HaboTribe2Lock(entry.runtime_data)])


class HaboTribe2Lock(HaboTribe2Entity, LockEntity):
    """Representation of a HABO Tribe2 smart lock."""

    _attr_has_entity_name = True
    _attr_translation_key = "lock"

    def __init__(self, coordinator: HaboTribe2Coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.device_id}_lock"

    @property
    def is_locked(self) -> bool | None:
        """Return true if the lock is locked."""

        return self.coordinator.data.is_locked

    @property
    def icon(self) -> str:
        """Return an icon that makes the locked state stand out."""

        if self.coordinator.data.is_locked is True:
            return "mdi:lock-alert"
        if self.coordinator.data.is_locked is False:
            return "mdi:lock-open-variant"
        return "mdi:lock-question"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional lock attributes."""

        data = self.coordinator.data
        return {
            ATTR_BATTERY_LEVEL: data.battery_level,
            ATTR_CONNECTED: data.connected,
            ATTR_DOOR_OPEN: data.door_open,
            ATTR_LAST_SEEN: data.last_seen,
            ATTR_LOCK_ADDR: data.lock_addr,
            ATTR_OPERATING_MODE: data.operating_mode,
            ATTR_VOLTAGE_MV: data.voltage_mv,
        }

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""

        try:
            await self.coordinator.client.async_lock(
                self.coordinator.gateway_id,
                self.coordinator.lock_addr,
            )
        except LockBusyError as err:
            raise HomeAssistantError("HABO lock is busy; try again shortly") from err
        except AuthenticationError as err:
            raise HomeAssistantError("HABO authentication failed") from err
        except HaboTribe2Error as err:
            raise HomeAssistantError(f"Failed to lock HABO lock: {err}") from err
        finally:
            with suppress(Exception):
                await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""

        try:
            await self.coordinator.client.async_unlock(
                self.coordinator.gateway_id,
                self.coordinator.lock_addr,
            )
        except LockBusyError as err:
            raise HomeAssistantError("HABO lock is busy; try again shortly") from err
        except AuthenticationError as err:
            raise HomeAssistantError("HABO authentication failed") from err
        except HaboTribe2Error as err:
            raise HomeAssistantError(f"Failed to unlock HABO lock: {err}") from err
        finally:
            with suppress(Exception):
                await self.coordinator.async_request_refresh()
