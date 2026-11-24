"""Diagnostics support for HABO Tribe2 Smart Lock."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator = entry.runtime_data
    data = coordinator.data

    return {
        "last_update_success": coordinator.last_update_success,
        "recent_requests": coordinator.client.recent_request_metadata,
        "battery_level": data.battery_level,
        "connected": data.connected,
    }
