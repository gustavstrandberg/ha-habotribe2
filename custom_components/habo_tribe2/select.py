"""Select platform for HABO Tribe2 Smart Lock."""

from __future__ import annotations

from contextlib import suppress

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import AuthenticationError, HaboTribe2Error, LockBusyError
from .const import DOMAIN
from .coordinator import HaboTribe2Coordinator
from .entity import HaboTribe2Entity

MODE_OPTIONS = ["normal", "privacy", "passage"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HABO Tribe2 select entities."""

    async_add_entities([HaboTribe2OperatingModeSelect(entry.runtime_data)])


class HaboTribe2OperatingModeSelect(HaboTribe2Entity, SelectEntity):
    """Select entity for the lock operating mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "operating_mode"
    _attr_options = MODE_OPTIONS

    def __init__(self, coordinator: HaboTribe2Coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.device_id}_operating_mode"

    @property
    def current_option(self) -> str | None:
        """Return the current operating mode."""

        return self.coordinator.data.operating_mode

    async def async_select_option(self, option: str) -> None:
        """Change the operating mode."""

        if option not in MODE_OPTIONS:
            raise HomeAssistantError(f"Unsupported HABO operating mode: {option}")

        try:
            await self.coordinator.client.async_set_operating_mode(
                self.coordinator.gateway_id,
                self.coordinator.lock_addr,
                option,
            )
        except LockBusyError as err:
            raise HomeAssistantError("HABO lock is busy; try again shortly") from err
        except AuthenticationError as err:
            raise HomeAssistantError("HABO authentication failed") from err
        except HaboTribe2Error as err:
            raise HomeAssistantError(f"Failed to set HABO operating mode: {err}") from err
        finally:
            with suppress(Exception):
                await self.coordinator.async_request_refresh()
