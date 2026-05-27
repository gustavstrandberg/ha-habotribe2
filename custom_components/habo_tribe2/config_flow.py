"""Config flow for HABO Tribe2 Smart Lock."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .api import (
    ApiSchemaError,
    AuthenticationError,
    HaboTribe2Client,
    HaboTribe2Error,
    LockState,
)
from .const import (
    CONF_BASE_URL,
    CONF_DEVICE_ID,
    CONF_GATEWAY_ID,
    CONF_LOCK_ADDR,
    CONF_LOCK_NAME,
    CONF_PIN,
    DEFAULT_BASE_URL,
    DOMAIN,
)


class HaboTribe2ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HABO Tribe2 Smart Lock."""

    VERSION = 1
    _user_input: dict[str, Any]
    _locks: list[LockState]
    _reauth_entry: config_entries.ConfigEntry | None

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""

        return HaboTribe2OptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            client = HaboTribe2Client(
                base_url=user_input[CONF_BASE_URL],
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
            )
            try:
                await client.async_login()
                self._locks = await client.async_get_locks()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except ApiSchemaError:
                errors["base"] = "unexpected_response"
            except HaboTribe2Error:
                errors["base"] = "cannot_connect"
            else:
                self._user_input = user_input
                return await self.async_step_lock()
            finally:
                await client.async_close()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Handle a reauthentication request."""

        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if self._reauth_entry is None:
            return self.async_abort(reason="unknown")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Confirm reauthentication credentials."""

        errors: dict[str, str] = {}

        if user_input is not None:
            if self._reauth_entry is None:
                return self.async_abort(reason="unknown")
            data = {
                key: value
                for key, value in {**self._reauth_entry.data, **user_input}.items()
                if key != "device_token"
            }
            client = HaboTribe2Client(
                base_url=data[CONF_BASE_URL],
                username=data[CONF_USERNAME],
                password=data[CONF_PASSWORD],
            )
            try:
                await client.async_login()
                await client.async_get_lock(data[CONF_DEVICE_ID])
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except ApiSchemaError:
                errors["base"] = "unexpected_response"
            except HaboTribe2Error:
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data=data,
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            finally:
                await client.async_close()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_lock(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Let the user choose a lock returned by the account."""

        errors: dict[str, str] = {}
        lock_map = {
            lock.device_id: f"{lock.name or lock.device_id} ({lock.lock_addr})"
            for lock in self._locks
        }

        if user_input is not None:
            selected_lock = next(
                (
                    lock
                    for lock in self._locks
                    if lock.device_id == user_input[CONF_DEVICE_ID]
                ),
                None,
            )
            if selected_lock is None:
                errors["base"] = "unknown_lock"
                return self.async_show_form(
                    step_id="lock",
                    data_schema=vol.Schema(
                        {vol.Required(CONF_DEVICE_ID): vol.In(lock_map)}
                    ),
                    errors=errors,
                )

            await self.async_set_unique_id(selected_lock.device_id)
            self._abort_if_unique_id_configured()

            data = {
                **self._user_input,
                CONF_DEVICE_ID: selected_lock.device_id,
                CONF_GATEWAY_ID: selected_lock.gateway_id,
                CONF_LOCK_ADDR: selected_lock.lock_addr,
                CONF_LOCK_NAME: selected_lock.name or selected_lock.device_id,
            }
            return self.async_create_entry(title=data[CONF_LOCK_NAME], data=data)

        if not lock_map:
            errors["base"] = "no_locks"

        return self.async_show_form(
            step_id="lock",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE_ID): vol.In(lock_map)}),
            errors=errors,
        )


class HaboTribe2OptionsFlow(config_entries.OptionsFlow):
    """Handle options for HABO Tribe2 Smart Lock."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Manage integration options."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PIN,
                        default=self._config_entry.options.get(CONF_PIN, ""),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                }
            ),
        )
