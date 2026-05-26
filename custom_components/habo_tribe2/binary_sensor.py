"""Binary sensor platform for HABO Tribe2 Smart Lock."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import LockState
from .const import DOMAIN
from .coordinator import HaboTribe2Coordinator
from .entity import HaboTribe2Entity


@dataclass(frozen=True, kw_only=True)
class HaboTribe2BinarySensorDescription(BinarySensorEntityDescription):
    """Description for a HABO Tribe2 binary sensor."""

    value_fn: Callable[[LockState], bool | None]


BINARY_SENSOR_DESCRIPTIONS = (
    HaboTribe2BinarySensorDescription(
        key="door",
        translation_key="door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda data: data.door_open,
    ),
    HaboTribe2BinarySensorDescription(
        key="connected",
        translation_key="connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: data.connected,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HABO Tribe2 binary sensors."""

    coordinator: HaboTribe2Coordinator = entry.runtime_data
    async_add_entities(
        HaboTribe2BinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class HaboTribe2BinarySensor(HaboTribe2Entity, BinarySensorEntity):
    """Representation of a HABO Tribe2 binary sensor."""

    entity_description: HaboTribe2BinarySensorDescription

    def __init__(
        self,
        coordinator: HaboTribe2Coordinator,
        description: HaboTribe2BinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{coordinator.device_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""

        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Keep the connectivity sensor available while reporting offline."""

        if self.entity_description.key == "connected":
            return self.coordinator.last_update_success
        return super().available
