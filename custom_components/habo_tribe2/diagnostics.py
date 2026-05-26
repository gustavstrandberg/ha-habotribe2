"""Diagnostics support for HABO Tribe2 Smart Lock."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_TOKEN, CONF_PIN

TO_REDACT = {
    CONF_PASSWORD,
    CONF_PIN,
    CONF_DEVICE_TOKEN,
    CONF_USERNAME,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator = entry.runtime_data
    data = coordinator.data

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "parsed_state": {
            "device_id": data.device_id,
            "gateway_id": data.gateway_id,
            "lock_addr": data.lock_addr,
            "name": data.name,
            "is_locked": data.is_locked,
            "battery_level": data.battery_level,
            "connected": data.connected,
            "door_open": data.door_open,
            "operating_mode": data.operating_mode,
            "voltage_mv": data.voltage_mv,
        },
    }
