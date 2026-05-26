"""Cloud client for HABO Tribe2 Smart Lock."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import httpx

_LOGGER = logging.getLogger(__name__)


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
class LockState:
    """Normalized state for one HABO Tribe2 lock."""

    device_id: str
    gateway_id: str
    lock_addr: int
    name: str | None
    is_locked: bool | None
    battery_level: int | None = None
    connected: bool | None = None
    door_open: bool | None = None
    last_seen: str | None = None
    operating_mode: str | None = None
    voltage_mv: int | None = None


class HaboTribe2Client:
    """Minimal async API client for the HABO Tribe2 cloud."""

    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        device_token: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._device_token = device_token or ""
        self._client = client or httpx.AsyncClient(timeout=20)
        self._owns_client = client is None
        self._token: str | None = None

    async def async_close(self) -> None:
        """Close the underlying HTTP client."""

        if self._owns_client:
            await self._client.aclose()

    async def async_login(self) -> None:
        """Authenticate with the cloud service."""

        payload = {
            "email": self._username,
            "deviceToken": self._device_token,
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
        return _parse_lock_list(data)

    async def async_get_lock(self, device_id: str) -> LockState:
        """Fetch and normalize a single lock state."""

        for lock in await self.async_get_locks():
            if lock.device_id == device_id or str(lock.lock_addr) == device_id:
                return lock
        raise ApiSchemaError(f"Lock {device_id} was not returned by the cloud")

    async def async_lock(self, gateway_id: str, lock_addr: int, pin: str) -> None:
        """Send a lock command."""

        data = await self._request(
            "POST",
            f"/doorlocks/{gateway_id}/{lock_addr}/lock",
            params={"pin": pin},
        )
        _raise_if_command_failed(data)

    async def async_unlock(
        self,
        gateway_id: str,
        lock_addr: int,
        pin: str,
        timeout: int = 5000,
    ) -> None:
        """Send an unlock command."""

        data = await self._request(
            "POST",
            f"/doorlocks/{gateway_id}/{lock_addr}/unlock",
            params={"pin": pin, "timeout": timeout},
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
    voltage_mv = _coerce_raw_int(info.get("vrm"))
    return LockState(
        device_id=str(device_id),
        gateway_id=gateway_id,
        lock_addr=lock_addr,
        name=_first_str(data, "name") or _first_str(info, "name"),
        is_locked=lock_state,
        battery_level=_battery_percent_from_voltage(voltage_mv),
        connected=_coerce_bool(info.get("connected")),
        door_open=_coerce_bool(info.get("doorState")),
        last_seen=_first_str(data, "mqttLastUpdate") or _first_str(data, "lastUpdate"),
        operating_mode=operating_mode,
        voltage_mv=voltage_mv,
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


def _battery_percent_from_voltage(value: int | None) -> int | None:
    """Estimate battery level from the millivolt-like `vrm` field."""

    if value is None:
        return None
    return max(0, min(100, round((value - 4500) / (6500 - 4500) * 100)))
