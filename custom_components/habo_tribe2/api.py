"""Cloud client for HABO Tribe2 Smart Lock."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import logging
from time import monotonic
from typing import Any

import httpx

_LOGGER = logging.getLogger(__name__)
GATEWAY_INFO_TTL_SECONDS = 12 * 60 * 60
LOCK_INFO_ATTR = 65527


class HaboTribe2Error(Exception):
    """Base error for HABO Tribe2 API failures."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        api_code: int | None = None,
        api_error: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.api_code = api_code
        self.api_error = api_error


class AuthenticationError(HaboTribe2Error):
    """Raised when the cloud rejects credentials."""


class CommandError(HaboTribe2Error):
    """Raised when a lock command is rejected by the cloud or lock."""


class LockBusyError(CommandError):
    """Raised when the lock or gateway is busy."""


class ApiSchemaError(HaboTribe2Error):
    """Raised when the cloud response does not match the expected shape."""


@dataclass(slots=True)
class EventLogEntry:
    """Normalized event log entry."""

    event_id: int | None = None
    date: str | None = None
    log_owner_id: str | None = None
    severity: str | None = None
    event_type: str | None = None
    text: str | None = None
    gateway_id: str | None = None
    lock_addr: int | None = None
    event_code: str | None = None
    event_source: str | None = None
    event_title: str | None = None
    user_id: int | None = None
    timestamp: str | None = None


@dataclass(slots=True)
class GatewayState:
    """Normalized state for one HABO SmartBox."""

    gateway_id: str
    name: str | None = None
    model: str | None = None
    serial_number: str | None = None
    firmware_version: str | int | None = None
    state: str | None = None
    mode: str | int | None = None
    address: str | int | None = None
    subnet: str | None = None
    gateway: str | None = None
    dns_main: str | None = None
    dns_backup: str | None = None
    zigbee_channel: int | None = None
    zigbee_pan_id: str | None = None
    last_seen: str | None = None


@dataclass(slots=True)
class LockState:
    """Normalized state for one HABO Tribe2 lock."""

    device_id: str
    gateway_id: str
    lock_addr: int
    name: str | None
    is_locked: bool | None
    model: str | None = None
    serial_number: str | None = None
    firmware_version: str | None = None
    battery_level: int | None = None
    connected: bool | None = None
    door_open: bool | None = None
    door_state: str | None = None
    bolt_state: str | None = None
    last_seen: str | None = None
    operating_mode: str | None = None
    scheduled_mode: str | None = None
    rssi: int | None = None
    tx_power: int | None = None
    total_run_time: int | None = None
    open_time: int | None = None
    unlock_events: int | None = None
    voltage_mv: int | None = None
    smartbox: GatewayState | None = None
    events: list[EventLogEntry] | None = None
    smartbox_events: list[EventLogEntry] | None = None
    admin_pin: str | None = None


class HaboTribe2Client:
    """Minimal async API client for the HABO Tribe2 cloud."""

    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._client = client or httpx.AsyncClient(timeout=20)
        self._owns_client = client is None
        self._token: str | None = None
        self._gateway_info_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock_info_cache: dict[str, tuple[float, dict[str, int]]] = {}

    async def async_close(self) -> None:
        """Close the underlying HTTP client."""

        if self._owns_client:
            await self._client.aclose()

    async def async_login(self) -> None:
        """Authenticate with the cloud service."""

        payload = {
            "email": self._username,
            "password": self._password,
        }
        data = await self._request("POST", "/account/login", json=payload, authenticate=False)
        if not isinstance(data, dict):
            raise AuthenticationError("Login returned an unexpected response")

        token = _deep_get(data, ("token",), ("data", "token"), ("accessToken",))
        if not isinstance(token, str) or not token:
            raise AuthenticationError("Login succeeded but no token was returned")
        self._token = token

    async def async_get_locks(self) -> list[LockState]:
        """Fetch all locks visible to the account."""

        data = await self._request("GET", "/doorlocks")
        locks = _parse_lock_list(data)
        try:
            gateways = await self.async_get_gateways()
        except HaboTribe2Error as err:
            _LOGGER.debug("Unable to fetch HABO SmartBox list: %s", err)
            gateways = {}
        try:
            events = await self.async_get_logs()
        except HaboTribe2Error as err:
            _LOGGER.debug("Unable to fetch HABO event logs: %s", err)
            events = []
        for lock in locks:
            try:
                _with_lock_info(
                    lock,
                    await self.async_get_lock_info(lock.gateway_id, lock.lock_addr),
                )
            except HaboTribe2Error as err:
                _LOGGER.debug("Unable to fetch HABO Doorlock Info: %s", err)
        return [
            _with_events(_with_gateway(lock, gateways.get(lock.gateway_id)), events)
            for lock in locks
        ]

    async def async_get_gateways(self) -> dict[str, GatewayState]:
        """Fetch all SmartBoxes visible to the account."""

        data = await self._request("GET", "/gw/list")
        gateways = _parse_gateway_map(data)
        for gateway_id, gateway in gateways.items():
            try:
                _with_gateway_ip_config(
                    gateway,
                    await self.async_get_gateway_ip_config(
                        gateway_id,
                        _gateway_nic_type(gateway),
                    ),
                )
            except HaboTribe2Error as err:
                _LOGGER.debug("Unable to fetch HABO SmartBox IP config: %s", err)
        return gateways

    async def async_get_gateway_ip_config(
        self,
        gateway_id: str,
        nic_type: str = "Eth",
    ) -> dict[str, Any]:
        """Fetch cached SmartBox network configuration."""

        now = monotonic()
        cache_key = f"{gateway_id}:{nic_type}"
        cached = self._gateway_info_cache.get(cache_key)
        if cached is not None and now - cached[0] < GATEWAY_INFO_TTL_SECONDS:
            return cached[1]

        data = await self._request(
            "GET",
            f"/gw/{gateway_id}/config/get-ip",
            params={"nicType": nic_type},
        )
        config = _parse_gateway_ip_config(data)
        self._gateway_info_cache[cache_key] = (now, config)
        return config

    async def async_get_lock_info(self, gateway_id: str, lock_addr: int) -> dict[str, int]:
        """Fetch cached Doorlock Info counters."""

        now = monotonic()
        cache_key = f"{gateway_id}:{lock_addr}"
        cached = self._lock_info_cache.get(cache_key)
        if cached is not None and now - cached[0] < GATEWAY_INFO_TTL_SECONDS:
            return cached[1]

        data = await self._request(
            "GET",
            f"/doorlocks/{gateway_id}/{lock_addr}/attr",
            params={"attr": LOCK_INFO_ATTR},
        )
        info = _parse_lock_info_attr(data)
        self._lock_info_cache[cache_key] = (now, info)
        return info

    async def async_get_logs(self, take: int = 200) -> list[EventLogEntry]:
        """Fetch recent event logs."""

        data = await self._request("GET", "/logs/", params={"take": take})
        return _parse_event_logs(data)

    async def async_get_lock(self, device_id: str) -> LockState:
        """Fetch and normalize a single lock state."""

        for lock in await self.async_get_locks():
            if lock.device_id == device_id or str(lock.lock_addr) == device_id:
                return lock
        raise ApiSchemaError(f"Lock {device_id} was not returned by the cloud")

    async def async_lock(
        self,
        gateway_id: str,
        lock_addr: int,
        pin: str | None = None,
    ) -> None:
        """Send a lock command."""

        kwargs = {"params": {"pin": pin}} if pin else {}
        data = await self._request(
            "POST",
            f"/doorlocks/{gateway_id}/{lock_addr}/lock",
            **kwargs,
        )
        _raise_if_command_failed(data)

    async def async_unlock(
        self,
        gateway_id: str,
        lock_addr: int,
        timeout: int = 5000,
        *,
        pin: str | None = None,
    ) -> None:
        """Send an unlock command."""

        params: dict[str, int | str] = {"timeout": timeout}
        if pin:
            params["pin"] = pin
        data = await self._request(
            "POST",
            f"/doorlocks/{gateway_id}/{lock_addr}/unlock",
            params=params,
        )
        _raise_if_command_failed(data)

    async def async_set_operating_mode(
        self,
        gateway_id: str,
        lock_addr: int,
        mode: str,
    ) -> None:
        """Set lock operating mode.

        HABO uses attribute 65317 with a one-byte base64 payload:
        normal=AA==, privacy=Ag==, passage=BA==.
        """

        payload_by_mode = {
            "normal": "AA==",
            "privacy": "Ag==",
            "passage": "BA==",
        }
        data = await self._request(
            "POST",
            f"/doorlocks/{gateway_id}/{lock_addr}/attr",
            params={"attr": 65317},
            json=payload_by_mode[mode],
        )
        _raise_if_command_failed(data)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        authenticate: bool = True,
        **kwargs: Any,
    ) -> Any:
        if authenticate and self._token is None:
            await self.async_login()

        headers = dict(kwargs.pop("headers", {}))
        headers.setdefault("Content-Type", "application/json")
        headers.setdefault("Accept", "*/*")
        headers.setdefault("Accept-Language", "sv-SE,sv;q=0.9")
        headers.setdefault("Cache-Control", "no-cache")
        headers.setdefault("User-Agent", "HABO%20Tribe/1 CFNetwork/1404.0.5 Darwin/22.3.0")
        if authenticate and self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        url = f"{self._base_url}{path}"
        try:
            response = await self._client.request(method, url, headers=headers, **kwargs)
        except httpx.TimeoutException as err:
            raise HaboTribe2Error("Connection to HABO cloud timed out") from err
        except httpx.ConnectError as err:
            raise HaboTribe2Error("Unable to connect to HABO cloud") from err
        except httpx.HTTPError as err:
            raise HaboTribe2Error(f"HABO cloud request failed: {err}") from err

        if response.status_code in (401, 403):
            if authenticate and self._token is not None:
                self._token = None
            api_code, api_error = _extract_api_error(response)
            raise AuthenticationError(
                _format_api_error("Authentication failed", response, api_code, api_error),
                status_code=response.status_code,
                api_code=api_code,
                api_error=api_error,
            )
        if not authenticate and path == "/account/login" and response.status_code >= 400:
            api_code, api_error = _extract_api_error(response)
            raise AuthenticationError(
                _format_api_error("Login failed", response, api_code, api_error),
                status_code=response.status_code,
                api_code=api_code,
                api_error=api_error,
            )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as err:
            api_code, api_error = _extract_api_error(response)
            exception_class = LockBusyError if api_code == 305 or api_error == "Busy" else HaboTribe2Error
            raise exception_class(
                _format_api_error("HABO cloud rejected the request", response, api_code, api_error),
                status_code=response.status_code,
                api_code=api_code,
                api_error=api_error,
            ) from err

        if not response.content:
            return None

        try:
            data = response.json()
        except ValueError as err:
            raise ApiSchemaError("HABO cloud returned a non-JSON response") from err

        _LOGGER.debug("HABO Tribe2 %s %s returned HTTP %s", method, path, response.status_code)
        return data


def _parse_lock_list(data: Any) -> list[LockState]:
    """Parse the /doorlocks response."""

    if isinstance(data, dict):
        raw_locks = data.get("owned", [])
    else:
        raw_locks = data

    if not isinstance(raw_locks, list):
        raise ApiSchemaError("Doorlocks response does not contain a lock list")

    return [_parse_lock_state(lock) for lock in raw_locks if isinstance(lock, dict)]


def _parse_gateway_map(data: Any) -> dict[str, GatewayState]:
    """Parse the /gw/list response."""

    if not isinstance(data, list):
        raise ApiSchemaError("Gateway response does not contain a gateway list")

    gateways: dict[str, GatewayState] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        gateway_id = item.get("id")
        if not isinstance(gateway_id, str):
            continue
        gateways[gateway_id] = _parse_gateway_state(item)
    return gateways


def _parse_event_logs(data: Any) -> list[EventLogEntry]:
    """Parse the /logs response."""

    if not isinstance(data, list):
        raise ApiSchemaError("Logs response does not contain a log list")

    return [_parse_event_log_entry(item) for item in data if isinstance(item, dict)]


def _parse_event_log_entry(data: dict[str, Any]) -> EventLogEntry:
    payload = data.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    text = _first_str(data, "text")
    event_title = _first_str(payload, "eventTitle")
    return EventLogEntry(
        event_id=_coerce_raw_int(data.get("id")),
        date=_first_str(data, "date"),
        log_owner_id=_first_str(data, "logOwnerId"),
        severity=_first_str(data, "severity"),
        event_type=_first_str(data, "type") or _first_str(payload, "eventType"),
        text=text,
        gateway_id=_first_str(payload, "gateway"),
        lock_addr=_coerce_raw_int(payload.get("device")),
        event_code=_first_str(payload, "eventCode"),
        event_source=_first_str(payload, "eventSource"),
        event_title=event_title,
        user_id=_coerce_raw_int(payload.get("userId")),
        timestamp=_first_str(payload, "timestamp"),
    )


def _parse_gateway_state(data: dict[str, Any]) -> GatewayState:
    payload = data.get("mqttPayload")
    if not isinstance(payload, dict):
        payload = {}

    gateway_id = data.get("id") or payload.get("id")
    if not isinstance(gateway_id, str):
        raise ApiSchemaError("Gateway identifiers are missing")

    return GatewayState(
        gateway_id=gateway_id,
        name=_first_str(data, "name") or _first_str(payload, "name"),
        model=_first_str(payload, "model") or _first_str(data, "model"),
        serial_number=_first_str(data, "serialNumber") or _first_str(payload, "serialNumber"),
        firmware_version=_firmware_version_string(
            _first_present(payload, "firmwareVersion", "swBuild", "firmware")
        ),
        state=_first_str(payload, "state") or _first_str(data, "state"),
        mode=_first_present(payload, "mode", "networkMode", "opMode"),
        address=_first_present(payload, "address", "ipAddress", "ip", "addr"),
        subnet=_first_str(payload, "subnet", "subnetMask", "netmask"),
        gateway=_first_str(payload, "gateway", "defaultGateway", "router"),
        dns_main=_first_str(payload, "dnsMain", "dns1", "primaryDns"),
        dns_backup=_first_str(payload, "dnsBackup", "dns2", "secondaryDns"),
        zigbee_channel=_coerce_raw_int(payload.get("channel")),
        zigbee_pan_id=_hex_string(payload.get("panID")),
        last_seen=_first_str(data, "mqttLastUpdate", "lastUpdate"),
    )


def _parse_gateway_ip_config(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ApiSchemaError("Gateway IP config response does not contain an object")
    return data


def _parse_lock_info_attr(data: Any) -> dict[str, int]:
    if not isinstance(data, str):
        raise ApiSchemaError("Doorlock Info response does not contain a base64 payload")

    try:
        payload = base64.b64decode(data, validate=True)
    except binascii.Error as err:
        raise ApiSchemaError("Doorlock Info response is not valid base64") from err

    if len(payload) < 16:
        raise ApiSchemaError("Doorlock Info response is too short")

    return {
        "total_run_time": int.from_bytes(payload[0:4], "little"),
        "open_time": int.from_bytes(payload[4:8], "little"),
        "unlock_events": int.from_bytes(payload[8:12], "little"),
    }


def _gateway_nic_type(gateway: GatewayState) -> str:
    values = (gateway.state, gateway.mode)
    if any(isinstance(value, str) and "wifi" in value.lower() for value in values):
        return "Wifi"
    return "Eth"


def _with_gateway_ip_config(gateway: GatewayState, config: dict[str, Any]) -> GatewayState:
    is_static = config.get("isStatic")
    if isinstance(is_static, bool):
        gateway.mode = "static" if is_static else "dhcp"

    gateway.address = _first_str(config, "addressString") or gateway.address
    gateway.subnet = _first_str(config, "subnetMaskString") or gateway.subnet
    gateway.gateway = _first_str(config, "gatewayString") or gateway.gateway
    gateway.dns_main = _first_str(config, "dnS1String", "dns1String") or gateway.dns_main
    gateway.dns_backup = _first_str(config, "dnS2String", "dns2String") or gateway.dns_backup
    return gateway


def _with_gateway(lock: LockState, gateway: GatewayState | None) -> LockState:
    lock.smartbox = gateway
    return lock


def _with_lock_info(lock: LockState, info: dict[str, int]) -> LockState:
    lock.total_run_time = info.get("total_run_time", lock.total_run_time)
    lock.open_time = info.get("open_time", lock.open_time)
    lock.unlock_events = info.get("unlock_events", lock.unlock_events)
    return lock


def _with_events(lock: LockState, events: list[EventLogEntry]) -> LockState:
    lock.events = [
        event
        for event in events
        if event.gateway_id == lock.gateway_id and event.lock_addr == lock.lock_addr
    ]
    lock.smartbox_events = [
        event
        for event in events
        if event.gateway_id == lock.gateway_id and event.lock_addr is None
    ]
    return lock


def _raise_if_command_failed(data: Any) -> None:
    """Raise a typed exception when the API returns an error object."""

    if data in (None, "Ok"):
        return

    if isinstance(data, dict):
        api_code = _coerce_raw_int(data.get("code"))
        api_error = data.get("error")
        if not isinstance(api_error, str):
            api_error = data.get("message")
        if api_code is None and api_error is None:
            return

        exception_class = LockBusyError if api_code == 305 or api_error == "Busy" else CommandError
        raise exception_class(
            _format_api_error("HABO command failed", None, api_code, api_error),
            api_code=api_code,
            api_error=api_error,
        )

    raise ApiSchemaError(f"HABO command returned an unexpected response: {data!r}")


def _extract_api_error(response: httpx.Response) -> tuple[int | None, str | None]:
    try:
        data = response.json()
    except ValueError:
        return None, None

    if not isinstance(data, dict):
        return None, None

    api_code = _coerce_raw_int(data.get("code"))
    api_error = data.get("error")
    if not isinstance(api_error, str):
        api_error = data.get("message")
    if not isinstance(api_error, str):
        api_error = None
    return api_code, api_error


def _format_api_error(
    fallback: str,
    response: httpx.Response | None,
    api_code: int | None,
    api_error: str | None,
) -> str:
    details: list[str] = []
    if response is not None:
        details.append(f"HTTP {response.status_code}")
    if api_code is not None:
        details.append(f"code {api_code}")
    if api_error:
        details.append(api_error)
    return f"{fallback}: {', '.join(details)}" if details else fallback


def _parse_lock_state(data: dict[str, Any]) -> LockState:
    """Parse a HABO doorlock object into Home Assistant state."""

    info = data.get("info")
    if not isinstance(info, dict):
        raise ApiSchemaError("Doorlock is missing info")

    device_id = data.get("id")
    gateway_id = data.get("gatewayId")
    lock_addr = info.get("addr")
    if (
        not isinstance(device_id, int)
        or not isinstance(gateway_id, str)
        or not isinstance(lock_addr, int)
    ):
        raise ApiSchemaError("Doorlock identifiers are missing")

    lock_state = _coerce_locked(info.get("lockState"))
    operating_mode = _operating_mode_name(_coerce_int(info.get("opMode")))
    voltage_mv = _coerce_voltage_mv(info.get("vrm"))
    return LockState(
        device_id=str(device_id),
        gateway_id=gateway_id,
        lock_addr=lock_addr,
        name=_first_str(data, "name") or _first_str(info, "name"),
        is_locked=lock_state,
        model=_first_str(info, "model"),
        serial_number=_first_str(info, "serialNumber"),
        firmware_version=_first_str(info, "swBuild", "firmwareVersion"),
        battery_level=_battery_percent_from_voltage(voltage_mv),
        connected=_coerce_bool(info.get("connected")),
        door_open=_coerce_bool(info.get("doorState")),
        door_state=_door_state_name(_coerce_int(info.get("doorState"))),
        bolt_state=_bolt_state_name(_coerce_int(info.get("boltState"))),
        last_seen=_latest_timestamp(
            _first_str(data, "mqttLastUpdate", "lastUpdate"),
            _latest_child_update(data.get("openings")),
            _latest_child_update(data.get("fingerprints")),
        ),
        operating_mode=operating_mode,
        scheduled_mode=_scheduled_mode_name(_coerce_int(info.get("schMode"))),
        rssi=_coerce_raw_int(info.get("rssi")),
        tx_power=_coerce_raw_int(info.get("txPower")),
        total_run_time=_coerce_raw_int(
            _first_present(info, "totalRunTime", "totalRuntime", "runTime")
        ),
        open_time=_coerce_raw_int(_first_present(info, "openTime", "openings")),
        unlock_events=_coerce_raw_int(
            _first_present(info, "unlockEvents", "unlockCount", "openCount")
        ),
        voltage_mv=voltage_mv,
        admin_pin=_admin_pin_from_openings(data.get("openings")),
    )


def _deep_get(
    data: dict[str, Any],
    *paths: tuple[str, ...],
    default: Any = None,
) -> Any:
    for path in paths:
        current: Any = data
        for key in path:
            if not isinstance(current, dict) or key not in current:
                break
            current = current[key]
        else:
            return current
    return default


def _first_present(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def _first_str(data: dict[str, Any], *keys: str) -> str | None:
    value = _first_present(data, *keys)
    return value if isinstance(value, str) and value else None


def _admin_pin_from_openings(value: Any) -> str | None:
    if not isinstance(value, list):
        return None

    for item in value:
        if not isinstance(item, dict):
            continue
        if _coerce_raw_int(item.get("doorlockUserId")) != 0:
            continue
        return _first_str(item, "pin")

    return None


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "open", "opened"}:
            return True
        if normalized in {"false", "0", "no", "closed", "close"}:
            return False
    return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(0, min(100, value))
    if isinstance(value, str) and value.isdigit():
        return max(0, min(100, int(value)))
    return None


def _coerce_raw_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _hex_string(value: Any) -> str | None:
    if isinstance(value, str):
        normalized = value.strip().upper().removeprefix("0X")
        if normalized and all(character in "0123456789ABCDEF" for character in normalized):
            return normalized.zfill(4)
    raw = _coerce_raw_int(value)
    if raw is None:
        return None
    return f"{raw:04X}"


def _firmware_version_string(value: Any) -> str | int | None:
    if isinstance(value, str):
        return value

    raw = _coerce_raw_int(value)
    if raw is None:
        return None

    major = (raw >> 26) & 0x3F
    minor = (raw >> 20) & 0x0F
    patch = (raw >> 14) & 0x3F
    build = raw & 0x3FFF
    return f"{major}.{minor}.{patch}.{build}"


def _latest_child_update(value: Any) -> str | None:
    if not isinstance(value, list):
        return None
    updates = [
        update
        for item in value
        if isinstance(item, dict)
        for update in [_first_str(item, "lastUpdate", "mqttLastUpdate")]
        if update is not None
    ]
    return max(updates, default=None)


def _latest_timestamp(*values: str | None) -> str | None:
    timestamps = [value for value in values if value]
    return max(timestamps, default=None)


def _coerce_locked(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"locked", "lock", "closed", "close", "1", "true"}:
            return True
        if normalized in {"unlocked", "unlock", "open", "opened", "0", "false"}:
            return False
    return None


def _operating_mode_name(value: int | None) -> str | None:
    if value is None:
        return None
    return {
        0: "normal",
        2: "privacy",
        4: "passage",
    }.get(value, str(value))


def _door_state_name(value: int | None) -> str | None:
    if value is None:
        return None
    return {
        0: "closed",
        1: "open",
    }.get(value, str(value))


def _bolt_state_name(value: int | None) -> str | None:
    if value is None:
        return None
    return {
        0: "unlocked",
        1: "locked",
    }.get(value, str(value))


def _scheduled_mode_name(value: int | None) -> str | None:
    if value is None:
        return None
    return {
        0: "off",
        1: "on",
    }.get(value, str(value))


def _coerce_voltage_mv(value: Any) -> int | None:
    voltage = _coerce_raw_int(value)
    if voltage is None:
        return None
    if 3000 <= voltage <= 8000:
        return voltage
    _LOGGER.debug("Ignoring implausible HABO battery voltage value: %s", voltage)
    return None


def _battery_percent_from_voltage(value: int | None) -> int | None:
    """Estimate battery level from the millivolt-like `vrm` field."""

    if value is None:
        return None
    return max(0, min(100, round((value - 4500) / (6500 - 4500) * 100)))
