"""Constants for the HABO Tribe2 Smart Lock integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "habo_tribe2"
PLATFORMS = [Platform.BINARY_SENSOR, Platform.LOCK, Platform.SELECT, Platform.SENSOR]

CONF_BASE_URL = "base_url"
CONF_DEVICE_ID = "device_id"
CONF_GATEWAY_ID = "gateway_id"
CONF_LOCK_ADDR = "lock_addr"
CONF_LOCK_NAME = "lock_name"
CONF_API_RESPONSE_LOGGING = "api_response_logging"

DEFAULT_BASE_URL = "https://api.habotribe.com/api/v1"
DEFAULT_SCAN_INTERVAL_SECONDS = 60
DEFAULT_API_RESPONSE_LOG_LIMIT = 20

ATTR_BATTERY_LEVEL = "battery_level"
ATTR_CONNECTED = "connected"
ATTR_DOOR_OPEN = "door_open"
ATTR_LAST_SEEN = "last_seen"
ATTR_LOCK_ADDR = "lock_addr"
ATTR_OPERATING_MODE = "operating_mode"
ATTR_VOLTAGE_MV = "voltage_mv"
