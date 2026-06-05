"""Diagnostics support for HABO Tribe2 Smart Lock."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    "device_token",
    "pin",
    "admin_pin",
    "accessToken",
    "authorization",
    "token",
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
        "recent_api_json_responses": async_redact_data(
            coordinator.client.recent_json_responses,
            TO_REDACT,
        ),
        "parsed_state": {
            "device_id": data.device_id,
            "gateway_id": data.gateway_id,
            "lock_addr": data.lock_addr,
            "name": data.name,
            "is_locked": data.is_locked,
            "model": data.model,
            "serial_number": data.serial_number,
            "firmware_version": data.firmware_version,
            "battery_level": data.battery_level,
            "connected": data.connected,
            "door_open": data.door_open,
            "door_state": data.door_state,
            "bolt_state": data.bolt_state,
            "operating_mode": data.operating_mode,
            "scheduled_mode": data.scheduled_mode,
            "rssi": data.rssi,
            "tx_power": data.tx_power,
            "total_run_time": data.total_run_time,
            "open_time": data.open_time,
            "unlock_events": data.unlock_events,
            "voltage_mv": data.voltage_mv,
            "has_admin_pin": data.admin_pin is not None,
            "smartbox": asdict(data.smartbox) if data.smartbox else None,
        },
    }
