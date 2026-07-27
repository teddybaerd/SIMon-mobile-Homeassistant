"""Config flow for SIMon mobile."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import (
    SimonMobileAccountLocked,
    SimonMobileApi,
    SimonMobileAuthError,
    SimonMobileConnectionError,
    SimonMobileMfaRequired,
)
from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN


def _normalize_msisdn(value: str) -> str:
    """Normalize a German mobile number to international format."""
    compact = "".join(char for char in value.strip() if char.isdigit() or char == "+")
    if compact.startswith("00"):
        compact = f"+{compact[2:]}"
    elif compact.startswith("0"):
        compact = f"+49{compact[1:]}"
    elif compact.startswith("49"):
        compact = f"+{compact}"
    if not compact.startswith("+49") or not compact[1:].isdigit():
        raise vol.Invalid("invalid_msisdn")
    return compact


async def _validate_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Validate credentials and return unique ID plus normalized input."""
    data = {
        CONF_USERNAME: _normalize_msisdn(user_input[CONF_USERNAME]),
        CONF_PASSWORD: user_input[CONF_PASSWORD],
    }
    api = SimonMobileApi(
        async_get_clientsession(hass),
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
    )
    unique_id = await api.async_validate_login()
    return unique_id, data


class SimonMobileConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SIMon mobile."""

    VERSION = 1

    @staticmethod
    def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
        """Return the credential schema."""
        defaults = defaults or {}
        return vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME,
                    default=defaults.get(CONF_USERNAME, ""),
                ): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                unique_id, data = await _validate_input(self.hass, user_input)
            except vol.Invalid:
                errors["base"] = "invalid_msisdn"
            except SimonMobileMfaRequired:
                errors["base"] = "mfa_required"
            except SimonMobileAccountLocked:
                errors["base"] = "account_locked"
            except SimonMobileAuthError:
                errors["base"] = "invalid_auth"
            except SimonMobileConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"SIMon mobile · {unique_id[-4:]}",
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._schema(user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication."""
        self._reauth_entry = self._get_reauth_entry()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm updated credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                unique_id, data = await _validate_input(self.hass, user_input)
            except vol.Invalid:
                errors["base"] = "invalid_msisdn"
            except SimonMobileMfaRequired:
                errors["base"] = "mfa_required"
            except SimonMobileAccountLocked:
                errors["base"] = "account_locked"
            except SimonMobileAuthError:
                errors["base"] = "invalid_auth"
            except SimonMobileConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    data_updates=data,
                )

        defaults = {CONF_USERNAME: self._reauth_entry.data.get(CONF_USERNAME, "")}
        if user_input:
            defaults.update(user_input)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self._schema(defaults),
            errors=errors,
        )
