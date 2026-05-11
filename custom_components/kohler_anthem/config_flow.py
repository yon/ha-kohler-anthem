"""Config flow for Kohler Anthem integration."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_API_RESOURCE,
    CONF_APIM_KEY,
    CONF_B2C_REFRESH_TOKEN,
    CONF_CLIENT_ID,
    CONF_TENANT_ID,
    DOMAIN,
)
from kohler_anthem import KohlerAnthemClient, KohlerConfig
from kohler_anthem.exceptions import AuthenticationError, KohlerAnthemError

_LOGGER = logging.getLogger(__name__)


class _ValidationDone(Exception):
    """Internal sentinel: validation finished (success or specific error already set)."""

# Required for /commands/* writes (outlet on/off, presets, warmup, …).
# Kohler's backend now rejects ROPC-policy tokens on those endpoints with 403;
# B2C_1A_signin policy tokens are the only ones accepted. Seed once per account:
#
#   python -m kohler_anthem.b2c_signin url        # opens browser
#   # sign in, copy msauth:// URL from address bar
#   python -m kohler_anthem.b2c_signin exchange '<url>'
#
# The second command prints the refresh_token; paste it into the form.
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_APIM_KEY): cv.string,
        vol.Required(CONF_API_RESOURCE): cv.string,
        vol.Required(CONF_B2C_REFRESH_TOKEN): cv.string,
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_B2C_REFRESH_TOKEN): cv.string,
    }
)


class KohlerAnthemConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kohler Anthem."""

    VERSION = 1
    _reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return await self._async_validate_and_create(user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            description_placeholders={
                "docs_url": "https://github.com/yon/ha-kohler-anthem#setup"
            },
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Handle import from YAML configuration."""
        return await self._async_validate_and_create(import_data)

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Triggered when the stored b2c_refresh_token is revoked/expired."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Re-prompt the user for just the b2c_refresh_token field."""
        errors: dict[str, str] = {}
        entry = self._reauth_entry
        assert entry is not None

        if user_input is not None:
            # Validate the new refresh_token by trying a silent refresh
            new_token = user_input[CONF_B2C_REFRESH_TOKEN]
            config = KohlerConfig(
                username=entry.data[CONF_USERNAME],
                password=entry.data[CONF_PASSWORD],
                client_id=entry.data[CONF_CLIENT_ID],
                apim_subscription_key=entry.data[CONF_APIM_KEY],
                api_resource=entry.data[CONF_API_RESOURCE],
                b2c_refresh_token=new_token,
            )
            try:
                async with KohlerAnthemClient(config) as client:
                    await client._b2c_auth.refresh(client._session)
                    rotated = client.b2c_refresh_token or new_token
            except AuthenticationError as err:
                _LOGGER.error("Reauth refresh_token rejected: %s", err)
                errors[CONF_B2C_REFRESH_TOKEN] = "invalid_b2c_refresh_token"
            except KohlerAnthemError as err:
                _LOGGER.error("Reauth network error: %s", err)
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_B2C_REFRESH_TOKEN: rotated},
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "docs_url": "https://github.com/yon/ha-kohler-anthem#refresh-token",
            },
        )

    async def _async_validate_and_create(
        self, user_input: dict[str, Any]
    ) -> FlowResult:
        """Validate credentials and create config entry."""
        errors: dict[str, str] = {}

        config = KohlerConfig(
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
            client_id=user_input[CONF_CLIENT_ID],
            apim_subscription_key=user_input[CONF_APIM_KEY],
            api_resource=user_input[CONF_API_RESOURCE],
            b2c_refresh_token=user_input.get(CONF_B2C_REFRESH_TOKEN),
        )

        try:
            async with KohlerAnthemClient(config) as client:
                tenant_id = self._get_tenant_id(client)
                if not tenant_id:
                    errors["base"] = "cannot_discover"
                    raise _ValidationDone

                customer = await client.get_customer(tenant_id)
                devices = customer.get_all_devices()
                if devices:
                    _LOGGER.info(
                        "Found %d device(s) for tenant %s",
                        len(devices),
                        tenant_id,
                    )

                # Validate the B2C refresh_token by triggering a silent refresh.
                # If the token is bad, this raises AuthenticationError. If good,
                # we capture the rotated refresh_token to persist.
                rotated_token: str | None = None
                try:
                    await client._b2c_auth.refresh(client._session)
                    rotated_token = client.b2c_refresh_token
                except AuthenticationError as err:
                    _LOGGER.error("B2C refresh_token rejected: %s", err)
                    errors[CONF_B2C_REFRESH_TOKEN] = "invalid_b2c_refresh_token"
                    raise _ValidationDone from err

                await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Kohler Anthem ({user_input[CONF_USERNAME]})",
                    data={
                        **user_input,
                        CONF_TENANT_ID: tenant_id,
                        # Persist the rotated value so HA's next start has it
                        CONF_B2C_REFRESH_TOKEN: rotated_token
                        or user_input[CONF_B2C_REFRESH_TOKEN],
                    },
                )

        except _ValidationDone:
            pass
        except AuthenticationError as err:
            _LOGGER.error("Authentication failed: %s", err)
            errors["base"] = "invalid_auth"
        except KohlerAnthemError as err:
            _LOGGER.error("API error: %s", err)
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        # For import, abort on error rather than showing form
        if self.context.get("source") == config_entries.SOURCE_IMPORT:
            return self.async_abort(reason=errors.get("base", "unknown"))

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "docs_url": "https://github.com/yon/ha-kohler-anthem#setup"
            },
        )

    def _get_tenant_id(self, client: KohlerAnthemClient) -> str | None:
        """Extract tenant_id from the auth token."""
        if client._auth.token and client._auth.token.access_token:
            try:
                # JWT is three base64 parts separated by dots
                parts = client._auth.token.access_token.split(".")
                if len(parts) >= 2:
                    # Add padding if needed
                    payload = parts[1]
                    padding = 4 - len(payload) % 4
                    if padding != 4:
                        payload += "=" * padding
                    decoded = base64.urlsafe_b64decode(payload)
                    claims = json.loads(decoded)
                    # The 'oid' claim is the user's object ID (tenant_id)
                    return claims.get("oid") or claims.get("sub")
            except Exception as err:
                _LOGGER.warning("Could not decode access_token: %s", err)

        return None
