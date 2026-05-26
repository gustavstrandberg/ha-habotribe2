"""Sensor platform for HABO Tribe2 Smart Lock."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import LockState
from .const import DOMAIN
from .coordinator import HaboTribe2Coordinator
from .entity import HaboTribe2Entity


@dataclass(frozen=True, kw_only=True)
class HaboTribe2SensorDescription(SensorEntityDescription):
    """Description for a HABO Tribe2 sensor."""

    value_fn: Callable[[LockState], datetime | int | str | None]


SENSOR_DESCRIPTIONS = (
    HaboTribe2SensorDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.battery_level,
    ),
    HaboTribe2SensorDescription(
        key="voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.voltage_mv,
    ),
    HaboTribe2SensorDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _parse_timestamp(data.last_seen),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HABO Tribe2 sensors."""

    coordinator: HaboTribe2Coordinator = entry.runtime_data
    async_add_entities(
        HaboTribe2Sensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class HaboTribe2Sensor(HaboTribe2Entity, SensorEntity):
    """Representation of a HABO Tribe2 sensor."""

    entity_description: HaboTribe2SensorDescription

    def __init__(
        self,
        coordinator: HaboTribe2Coordinator,
        description: HaboTribe2SensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{coordinator.device_id}_{description.key}"

    @property
    def native_value(self) -> datetime | int | str | None:
        """Return the sensor state."""

        return self.entity_description.value_fn(self.coordinator.data)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
