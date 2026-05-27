"""HABO Tribe2 Smart Lock integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .api import HaboTribe2Client
from .const import CONF_BASE_URL, PLATFORMS
from .coordinator import HaboTribe2Coordinator

type HaboTribe2ConfigEntry = ConfigEntry[HaboTribe2Coordinator]

LEGACY_SECRET_KEYS = {"pin", "device_token"}


async def async_migrate_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Migrate old config entries."""

    if any(key in entry.data for key in LEGACY_SECRET_KEYS):
        data = {
            key: value
            for key, value in entry.data.items()
            if key not in LEGACY_SECRET_KEYS
        }
        hass.config_entries.async_update_entry(entry, data=data)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HaboTribe2ConfigEntry,
) -> bool:
    """Set up HABO Tribe2 Smart Lock from a config entry."""

    client = HaboTribe2Client(
        base_url=entry.data[CONF_BASE_URL],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )
    coordinator = HaboTribe2Coordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryError:
        await client.async_close()
        raise

    entry.runtime_data = coordinator
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await client.async_close()
        raise
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: HaboTribe2ConfigEntry,
) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.async_close()
    return unload_ok
