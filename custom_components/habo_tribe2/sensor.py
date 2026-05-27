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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import LockState
from .const import DOMAIN
from .coordinator import HaboTribe2Coordinator
from .entity import HaboTribe2Entity


@dataclass(frozen=True, kw_only=True)
class HaboTribe2SensorDescription(SensorEntityDescription):
    """Description for a HABO Tribe2 sensor."""

    value_fn: Callable[[LockState], datetime | int | str | None]
    device: str = "lock"


SENSOR_DESCRIPTIONS = (
    HaboTribe2SensorDescription(
        key="smartbox",
        translation_key="smartbox",
        value_fn=lambda data: _smartbox_value(data, "name"),
    ),
    HaboTribe2SensorDescription(
        key="model",
        translation_key="model",
        value_fn=lambda data: data.model,
    ),
    HaboTribe2SensorDescription(
        key="serial_number",
        translation_key="serial_number",
        value_fn=lambda data: data.serial_number,
    ),
    HaboTribe2SensorDescription(
        key="firmware_version",
        translation_key="firmware_version",
        value_fn=lambda data: data.firmware_version,
    ),
    HaboTribe2SensorDescription(
        key="lock_state",
        translation_key="lock_state",
        value_fn=lambda data: _lock_state_name(data),
    ),
    HaboTribe2SensorDescription(
        key="door_state",
        translation_key="door_state",
        value_fn=lambda data: data.door_state,
    ),
    HaboTribe2SensorDescription(
        key="bolt_state",
        translation_key="bolt_state",
        value_fn=lambda data: data.bolt_state,
    ),
    HaboTribe2SensorDescription(
        key="operating_mode",
        translation_key="operating_mode_sensor",
        value_fn=lambda data: data.operating_mode,
    ),
    HaboTribe2SensorDescription(
        key="scheduled_mode",
        translation_key="scheduled_mode",
        value_fn=lambda data: data.scheduled_mode,
    ),
    HaboTribe2SensorDescription(
        key="battery_level",
        translation_key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.battery_level,
    ),
    HaboTribe2SensorDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.voltage_mv,
    ),
    HaboTribe2SensorDescription(
        key="rssi",
        translation_key="rssi",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.rssi,
    ),
    HaboTribe2SensorDescription(
        key="tx_power",
        translation_key="tx_power",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.tx_power,
    ),
    HaboTribe2SensorDescription(
        key="total_run_time",
        translation_key="total_run_time",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.total_run_time,
    ),
    HaboTribe2SensorDescription(
        key="open_time",
        translation_key="open_time",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.open_time,
    ),
    HaboTribe2SensorDescription(
        key="unlock_events",
        translation_key="unlock_events",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.unlock_events,
    ),
    HaboTribe2SensorDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _parse_timestamp(data.last_seen),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_name",
        translation_key="smartbox_name",
        device="smartbox",
        value_fn=lambda data: _smartbox_value(data, "name"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_model",
        translation_key="smartbox_model",
        device="smartbox",
        value_fn=lambda data: _smartbox_value(data, "model"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_serial_number",
        translation_key="smartbox_serial_number",
        device="smartbox",
        value_fn=lambda data: _smartbox_value(data, "serial_number"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_firmware_version",
        translation_key="smartbox_firmware_version",
        device="smartbox",
        value_fn=lambda data: _smartbox_value(data, "firmware_version"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_state",
        translation_key="smartbox_state",
        device="smartbox",
        value_fn=lambda data: _smartbox_value(data, "state"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_mode",
        translation_key="smartbox_mode",
        device="smartbox",
        value_fn=lambda data: _smartbox_value(data, "mode"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_address",
        translation_key="smartbox_address",
        device="smartbox",
        value_fn=lambda data: _smartbox_value(data, "address"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_subnet",
        translation_key="smartbox_subnet",
        device="smartbox",
        value_fn=lambda data: _smartbox_value(data, "subnet"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_gateway",
        translation_key="smartbox_gateway",
        device="smartbox",
        value_fn=lambda data: _smartbox_value(data, "gateway"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_dns_main",
        translation_key="smartbox_dns_main",
        device="smartbox",
        value_fn=lambda data: _smartbox_value(data, "dns_main"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_dns_backup",
        translation_key="smartbox_dns_backup",
        device="smartbox",
        value_fn=lambda data: _smartbox_value(data, "dns_backup"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_zigbee_channel",
        translation_key="smartbox_zigbee_channel",
        device="smartbox",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _smartbox_value(data, "zigbee_channel"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_zigbee_pan_id",
        translation_key="smartbox_zigbee_pan_id",
        device="smartbox",
        value_fn=lambda data: _smartbox_value(data, "zigbee_pan_id"),
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
        if description.device == "smartbox":
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, coordinator.gateway_id)},
                manufacturer="HABO",
                model=_smartbox_value(coordinator.data, "model") or "SmartBox",
                name=_smartbox_value(coordinator.data, "name") or "HABO SmartBox",
                via_device=(DOMAIN, coordinator.device_id),
            )

    @property
    def native_value(self) -> datetime | int | str | None:
        """Return the sensor state."""

        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return if entity is available."""

        if self.entity_description.device == "smartbox":
            return (
                self.coordinator.last_update_success
                and self.coordinator.data.smartbox is not None
            )
        return super().available


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _lock_state_name(data: LockState) -> str | None:
    if data.is_locked is True:
        return "locked"
    if data.is_locked is False:
        return "unlocked"
    return None


def _smartbox_value(data: LockState, attr: str) -> int | str | None:
    if data.smartbox is None:
        return None
    value = getattr(data.smartbox, attr)
    if isinstance(value, bool):
        return str(value)
    return value
