"""Config flow for Kohler Anthem integration.

Replaces the legacy ROPC (username + password) flow with OAuth Authorization
Code + PKCE against the B2C_1A_signin policy. Three-step flow:

    1. ``user`` — collect ``client_id``, ``apim_subscription_key``,
       ``api_resource`` (still per-user values from credential extraction).
    2. ``authorize`` — show a clickable authorize URL and ask the user to
       paste back the URL their browser ends up at after sign-in.
    3. (internal) — exchange the code for tokens, persist, create entry.

Reauth follows the same path; the existing entry's data is updated rather
than a new entry created. YAML import is deliberately disabled — interactive
sign-in cannot be carried in YAML.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import asdict
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from kohler_anthem import (
    KohlerAnthemClient,
    KohlerAnthemError,
    KohlerOAuthAuth,
    KohlerOAuthConfig,
    TokenInfo,
)

from ._oauth_helpers import (
    decode_jwt_oid,
    extract_code_and_state,
    username_from_token,
)
from .const import (
    CONF_API_RESOURCE,
    CONF_APIM_KEY,
    CONF_CLIENT_ID,
    CONF_REDIRECT_URL,
    CONF_TENANT_ID,
    CONF_TOKEN,
    DOMAIN,
    OAUTH_REDIRECT_URI,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_APIM_KEY): cv.string,
        vol.Required(CONF_API_RESOURCE): cv.string,
    }
)

STEP_AUTHORIZE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_REDIRECT_URL): cv.string,
    }
)


class _StoreOnceTokenStore:
    """Trivial TokenStore for use during the config flow.

    The flow only needs to mint a token once and read it back in the same
    step; runtime persistence is handled by HA's config-entry storage in
    ``__init__.py`` after the entry exists.
    """

    def __init__(self) -> None:
        self.token: TokenInfo | None = None

    async def load(self) -> TokenInfo | None:
        return self.token

    async def save(self, token: TokenInfo) -> None:
        self.token = token


class KohlerAnthemConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kohler Anthem."""

    VERSION = 2

    def __init__(self) -> None:
        super().__init__()
        self._user_input: dict[str, Any] = {}
        self._pkce_verifier: str = ""
        self._state: str = ""
        self._authorize_url: str = ""
        self._reauth_entry: config_entries.ConfigEntry | None = None

    # ------------------------------------------------------------------
    # Step 1 — collect static credentials
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Collect client_id / apim_key / api_resource, then start OAuth."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                description_placeholders={
                    "docs_url": "https://github.com/yon/ha-kohler-anthem#setup"
                },
            )

        self._user_input = user_input
        return await self._async_prepare_authorize_step()

    # ------------------------------------------------------------------
    # Step 2 — show authorize URL, collect pasted-back redirect URL
    # ------------------------------------------------------------------

    async def _async_prepare_authorize_step(self) -> FlowResult:
        """Generate PKCE pair + authorize URL; render the authorize step."""
        config = self._build_oauth_config()
        verifier, challenge = KohlerOAuthAuth.generate_pkce_pair()
        state = secrets.token_urlsafe(16)
        # Build URL via the library so we never drift from how it's used at runtime.
        auth = KohlerOAuthAuth(config, token_store=_StoreOnceTokenStore())
        authorize_url = auth.build_authorize_url(state=state, code_challenge=challenge)

        self._pkce_verifier = verifier
        self._state = state
        self._authorize_url = authorize_url

        return self.async_show_form(
            step_id="authorize",
            data_schema=STEP_AUTHORIZE_SCHEMA,
            description_placeholders={
                "authorize_url": authorize_url,
                "redirect_uri": OAUTH_REDIRECT_URI,
            },
        )

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is None:
            return await self._async_prepare_authorize_step()

        code, state, error = extract_code_and_state(user_input[CONF_REDIRECT_URL])
        if error or not code or not state:
            _LOGGER.warning("OAuth redirect parse error: %s", error)
            return self.async_show_form(
                step_id="authorize",
                data_schema=STEP_AUTHORIZE_SCHEMA,
                errors={"base": "invalid_redirect"},
                description_placeholders={
                    "authorize_url": self._authorize_url,
                    "redirect_uri": OAUTH_REDIRECT_URI,
                },
            )
        if state != self._state:
            _LOGGER.warning("OAuth state mismatch")
            return self.async_show_form(
                step_id="authorize",
                data_schema=STEP_AUTHORIZE_SCHEMA,
                errors={"base": "state_mismatch"},
                description_placeholders={
                    "authorize_url": self._authorize_url,
                    "redirect_uri": OAUTH_REDIRECT_URI,
                },
            )

        return await self._async_exchange_and_finish(code)

    # ------------------------------------------------------------------
    # Step 3 — exchange code, validate, create/update entry
    # ------------------------------------------------------------------

    async def _async_exchange_and_finish(self, code: str) -> FlowResult:
        """Trade the code for tokens, verify it works, persist the entry."""
        config = self._build_oauth_config()
        store = _StoreOnceTokenStore()
        auth = KohlerOAuthAuth(config, token_store=store)
        session = async_get_clientsession(self.hass)
        try:
            token = await auth.exchange_code_for_token(
                session, code=code, code_verifier=self._pkce_verifier
            )
        except KohlerAnthemError as err:
            _LOGGER.error("Token exchange failed: %s", err)
            return self.async_show_form(
                step_id="authorize",
                data_schema=STEP_AUTHORIZE_SCHEMA,
                errors={"base": "token_exchange_failed"},
                description_placeholders={
                    "authorize_url": self._authorize_url,
                    "redirect_uri": OAUTH_REDIRECT_URI,
                    "error_detail": str(err),
                },
            )
        except aiohttp.ClientError as err:
            _LOGGER.error("Network error during token exchange: %s", err)
            return self.async_show_form(
                step_id="authorize",
                data_schema=STEP_AUTHORIZE_SCHEMA,
                errors={"base": "cannot_connect"},
                description_placeholders={
                    "authorize_url": self._authorize_url,
                    "redirect_uri": OAUTH_REDIRECT_URI,
                },
            )

        tenant_id = decode_jwt_oid(token.access_token)
        if tenant_id is None:
            _LOGGER.error("Could not extract tenant id from token claims")
            return self.async_abort(reason="missing_tenant_id")

        token_data = asdict(token)
        try:
            await self._verify_credentials_work(config, token_data, tenant_id)
        except KohlerAnthemError as err:
            _LOGGER.error("Credential verification failed: %s", err)
            return self.async_abort(reason="cannot_discover")

        username = self._reauth_username() or username_from_token(token.access_token) or tenant_id
        entry_data = {
            CONF_USERNAME: username,
            CONF_CLIENT_ID: self._user_input[CONF_CLIENT_ID],
            CONF_APIM_KEY: self._user_input[CONF_APIM_KEY],
            CONF_API_RESOURCE: self._user_input[CONF_API_RESOURCE],
            CONF_TENANT_ID: tenant_id,
            CONF_TOKEN: token_data,
        }

        if self._reauth_entry is not None:
            self.hass.config_entries.async_update_entry(
                self._reauth_entry, data=entry_data
            )
            await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        await self.async_set_unique_id(username.lower())
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"Kohler Anthem ({username})",
            data=entry_data,
        )

    async def _verify_credentials_work(
        self,
        config: KohlerOAuthConfig,
        token_data: dict[str, Any],
        tenant_id: str,
    ) -> None:
        """Connect with the new credentials and discover devices.

        Catches misconfigured app registrations / wrong APIM key early so the
        user gets feedback before the entry is saved.
        """
        store = _StoreOnceTokenStore()
        store.token = TokenInfo(**token_data)
        client = KohlerAnthemClient(config, token_store=store)
        await client.connect()
        try:
            customer = await client.get_customer(tenant_id)
            devices = customer.get_all_devices()
            _LOGGER.info("OAuth setup discovered %d device(s)", len(devices))
        finally:
            await client.close()

    # ------------------------------------------------------------------
    # YAML import — explicitly disabled (the legacy path required a password)
    # ------------------------------------------------------------------

    async def async_step_import(self, _import_data: dict[str, Any]) -> FlowResult:
        return self.async_abort(reason="manual_oauth_required")

    # ------------------------------------------------------------------
    # Reauth (called by HA when the runtime raises ReauthRequired)
    # ------------------------------------------------------------------

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if self._reauth_entry is None:
            return self.async_abort(reason="reauth_unknown_entry")
        # Reuse the static credentials from the existing entry; only the OAuth
        # token is missing/expired.
        self._user_input = {
            CONF_CLIENT_ID: self._reauth_entry.data[CONF_CLIENT_ID],
            CONF_APIM_KEY: self._reauth_entry.data[CONF_APIM_KEY],
            CONF_API_RESOURCE: self._reauth_entry.data[CONF_API_RESOURCE],
        }
        return await self._async_prepare_authorize_step()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_oauth_config(self) -> KohlerOAuthConfig:
        return KohlerOAuthConfig(
            client_id=self._user_input[CONF_CLIENT_ID],
            apim_subscription_key=self._user_input[CONF_APIM_KEY],
            api_resource=self._user_input[CONF_API_RESOURCE],
            redirect_uri=OAUTH_REDIRECT_URI,
        )

    def _reauth_username(self) -> str | None:
        if self._reauth_entry is None:
            return None
        username = self._reauth_entry.data.get(CONF_USERNAME)
        return username if isinstance(username, str) else None
