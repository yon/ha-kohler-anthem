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
    CONF_CLIENT_ID,
    CONF_TENANT_ID,
    DOMAIN,
)
from kohler_anthem import KohlerAnthemClient, KohlerConfig
from kohler_anthem.exceptions import AuthenticationError, KohlerAnthemError

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_APIM_KEY): cv.string,
        vol.Required(CONF_API_RESOURCE): cv.string,
    }
)


class KohlerAnthemConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kohler Anthem."""

    VERSION = 1

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

    async def async_step_import(
        self, import_data: dict[str, Any]
    ) -> FlowResult:
        """Handle import from YAML configuration."""
        return await self._async_validate_and_create(import_data)

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
        )

        try:
            async with KohlerAnthemClient(config) as client:
                tenant_id = self._get_tenant_id(client)
                if tenant_id:
                    customer = await client.get_customer(tenant_id)
                    devices = customer.get_all_devices()
                    if devices:
                        _LOGGER.info(
                            "Found %d device(s) for tenant %s",
                            len(devices),
                            tenant_id,
                        )

                    await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=f"Kohler Anthem ({user_input[CONF_USERNAME]})",
                        data={
                            **user_input,
                            CONF_TENANT_ID: tenant_id,
                        },
                    )
                else:
                    errors["base"] = "cannot_discover"

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
