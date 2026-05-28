"""Sensor platform for HABO Tribe2 Smart Lock."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

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
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EventLogEntry, LockState
from .const import DOMAIN
from .coordinator import HaboTribe2Coordinator
from .entity import HaboTribe2Entity
from .formatting import duration_text


@dataclass(frozen=True, kw_only=True)
class HaboTribe2SensorDescription(SensorEntityDescription):
    """Description for a HABO Tribe2 sensor."""

    value_fn: Callable[[LockState], datetime | int | str | None]
    attrs_fn: Callable[[LockState], dict[str, Any]] | None = None
    device: str = "lock"


SENSOR_DESCRIPTIONS = (
    HaboTribe2SensorDescription(
        key="smartbox",
        translation_key="smartbox",
        icon="mdi:hub-outline",
        value_fn=lambda data: _smartbox_value(data, "name"),
    ),
    HaboTribe2SensorDescription(
        key="model",
        translation_key="model",
        icon="mdi:form-textbox",
        value_fn=lambda data: data.model,
    ),
    HaboTribe2SensorDescription(
        key="serial_number",
        translation_key="serial_number",
        icon="mdi:barcode",
        value_fn=lambda data: data.serial_number,
    ),
    HaboTribe2SensorDescription(
        key="firmware_version",
        translation_key="firmware_version",
        icon="mdi:chip",
        value_fn=lambda data: data.firmware_version,
    ),
    HaboTribe2SensorDescription(
        key="lock_state",
        translation_key="lock_state",
        icon="mdi:lock-check",
        value_fn=lambda data: _lock_state_name(data),
    ),
    HaboTribe2SensorDescription(
        key="bolt_state",
        translation_key="bolt_state",
        icon="mdi:lock",
        value_fn=lambda data: data.bolt_state,
    ),
    HaboTribe2SensorDescription(
        key="operating_mode",
        translation_key="operating_mode_sensor",
        icon="mdi:tune-variant",
        value_fn=lambda data: data.operating_mode,
    ),
    HaboTribe2SensorDescription(
        key="scheduled_mode",
        translation_key="scheduled_mode",
        icon="mdi:calendar-clock",
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
        icon="mdi:signal",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.rssi,
    ),
    HaboTribe2SensorDescription(
        key="tx_power",
        translation_key="tx_power",
        icon="mdi:access-point",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.tx_power,
    ),
    HaboTribe2SensorDescription(
        key="total_run_time",
        translation_key="total_run_time",
        icon="mdi:timer-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: duration_text(data.total_run_time),
    ),
    HaboTribe2SensorDescription(
        key="open_time",
        translation_key="open_time",
        icon="mdi:door-open",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: duration_text(data.open_time),
    ),
    HaboTribe2SensorDescription(
        key="unlock_events",
        translation_key="unlock_events",
        icon="mdi:lock-open-check",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.unlock_events,
    ),
    HaboTribe2SensorDescription(
        key="last_seen",
        translation_key="last_seen",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: _last_seen_timestamp(data),
    ),
    HaboTribe2SensorDescription(
        key="event_log",
        translation_key="event_log",
        icon="mdi:clipboard-text-clock-outline",
        value_fn=lambda data: _latest_event_text(data.events),
        attrs_fn=lambda data: {"events": _event_attributes(data.events)},
    ),
    HaboTribe2SensorDescription(
        key="smartbox_name",
        translation_key="smartbox_name",
        device="smartbox",
        icon="mdi:rename-outline",
        value_fn=lambda data: _smartbox_value(data, "name"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_model",
        translation_key="smartbox_model",
        device="smartbox",
        icon="mdi:hub-outline",
        value_fn=lambda data: _smartbox_value(data, "model"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_serial_number",
        translation_key="smartbox_serial_number",
        device="smartbox",
        icon="mdi:barcode",
        value_fn=lambda data: _smartbox_value(data, "serial_number"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_firmware_version",
        translation_key="smartbox_firmware_version",
        device="smartbox",
        icon="mdi:chip",
        value_fn=lambda data: _smartbox_value(data, "firmware_version"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_state",
        translation_key="smartbox_state",
        device="smartbox",
        icon="mdi:cloud-check-outline",
        value_fn=lambda data: _smartbox_value(data, "state"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_mode",
        translation_key="smartbox_mode",
        device="smartbox",
        icon="mdi:tune-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _smartbox_value(data, "mode"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_address",
        translation_key="smartbox_address",
        device="smartbox",
        icon="mdi:ip-network-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _smartbox_value(data, "address"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_subnet",
        translation_key="smartbox_subnet",
        device="smartbox",
        icon="mdi:ip-network",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _smartbox_value(data, "subnet"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_gateway",
        translation_key="smartbox_gateway",
        device="smartbox",
        icon="mdi:router-network",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _smartbox_value(data, "gateway"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_dns_main",
        translation_key="smartbox_dns_main",
        device="smartbox",
        icon="mdi:dns-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _smartbox_value(data, "dns_main"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_dns_backup",
        translation_key="smartbox_dns_backup",
        device="smartbox",
        icon="mdi:dns-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _smartbox_value(data, "dns_backup"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_zigbee_channel",
        translation_key="smartbox_zigbee_channel",
        device="smartbox",
        icon="mdi:zigbee",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _smartbox_value(data, "zigbee_channel"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_zigbee_pan_id",
        translation_key="smartbox_zigbee_pan_id",
        device="smartbox",
        icon="mdi:identifier",
        value_fn=lambda data: _smartbox_value(data, "zigbee_pan_id"),
    ),
    HaboTribe2SensorDescription(
        key="smartbox_event_log",
        translation_key="smartbox_event_log",
        device="smartbox",
        icon="mdi:clipboard-text-clock-outline",
        value_fn=lambda data: _latest_event_text(data.smartbox_events),
        attrs_fn=lambda data: {"events": _event_attributes(data.smartbox_events)},
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
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return sensor attributes."""

        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return if entity is available."""

        if self.entity_description.device == "smartbox":
            return (
                self.coordinator.last_update_success
                and self.coordinator.data.smartbox is not None
                and self.native_value is not None
            )
        if self.entity_description.key in {
            "total_run_time",
            "open_time",
            "unlock_events",
        }:
            return self.coordinator.last_update_success and self.native_value is not None
        return super().available


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


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


def _last_seen_timestamp(data: LockState) -> datetime | None:
    return _parse_timestamp(data.last_seen or _latest_event_date(data.events))


def _latest_event_text(events: list[EventLogEntry] | None) -> str | None:
    if not events:
        return "No events"
    event = events[0]
    return event.event_title or event.text or event.event_code


def _latest_event_date(events: list[EventLogEntry] | None) -> str | None:
    if not events:
        return None
    return events[0].date


def _event_attributes(events: list[EventLogEntry] | None) -> list[dict[str, Any]]:
    if not events:
        return []
    return [
        {
            "id": event.event_id,
            "date": event.date,
            "log_owner_id": event.log_owner_id,
            "severity": event.severity,
            "type": event.event_type,
            "text": event.text,
            "event_code": event.event_code,
            "event_source": event.event_source,
            "event_title": event.event_title,
            "timestamp": event.timestamp,
            "user_id": event.user_id,
        }
        for event in events[:200]
    ]
