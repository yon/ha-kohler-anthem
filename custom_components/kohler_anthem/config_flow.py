"""Config flow for Kohler Anthem integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .lib import KohlerAnthemClient, KohlerConfig
from .lib.exceptions import AuthenticationError, KohlerAnthemError

from .const import (
    CONF_API_RESOURCE,
    CONF_APIM_KEY,
    CONF_CLIENT_ID,
    CONF_CUSTOMER_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)

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
        errors: dict[str, str] = {}

        if user_input is not None:
            config = KohlerConfig(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                client_id=user_input[CONF_CLIENT_ID],
                apim_subscription_key=user_input[CONF_APIM_KEY],
                api_resource=user_input[CONF_API_RESOURCE],
            )

            try:
                async with KohlerAnthemClient(config) as client:
                    # Try to discover devices to validate credentials
                    # Get customer_id from the token (stored after auth)
                    # For now we'll need to discover it
                    customer_id = await self._get_customer_id(client, config)
                    if customer_id:
                        customer = await client.get_customer(customer_id)
                        devices = customer.get_all_devices()
                        if devices:
                            _LOGGER.info(
                                "Found %d device(s) for customer %s",
                                len(devices),
                                customer_id,
                            )

                        await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                        self._abort_if_unique_id_configured()

                        return self.async_create_entry(
                            title=f"Kohler Anthem ({user_input[CONF_USERNAME]})",
                            data={
                                **user_input,
                                CONF_CUSTOMER_ID: customer_id,
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

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "docs_url": "https://github.com/yon/kohler-anthem-hacs#setup"
            },
        )

    async def _get_customer_id(
        self, client: KohlerAnthemClient, config: KohlerConfig
    ) -> str | None:
        """Extract customer_id from the auth token."""
        # The customer_id is embedded in the id_token (JWT)
        # We can decode the JWT payload (middle part) to get it
        import base64
        import json

        if client._auth.token and client._auth.token.id_token:
            try:
                # JWT is three base64 parts separated by dots
                parts = client._auth.token.id_token.split(".")
                if len(parts) >= 2:
                    # Add padding if needed
                    payload = parts[1]
                    padding = 4 - len(payload) % 4
                    if padding != 4:
                        payload += "=" * padding
                    decoded = base64.urlsafe_b64decode(payload)
                    claims = json.loads(decoded)
                    # The 'oid' claim is the user's object ID (customer_id)
                    customer_id = claims.get("oid") or claims.get("sub")
                    if customer_id:
                        return customer_id
            except Exception as err:
                _LOGGER.warning("Could not decode id_token: %s", err)

        return None
