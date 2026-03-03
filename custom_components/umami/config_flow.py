"""Config flow for Umami Analytics."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import UmamiApiClient, UmamiAuthError, UmamiConnectionError
from .const import (
    DOMAIN,
    CONF_URL,
    CONF_AUTH_TYPE,
    CONF_API_KEY,
    CONF_SITES,
    CONF_TIME_RANGE,
    CONF_UPDATE_INTERVAL,
    AUTH_TYPE_SELF_HOSTED,
    AUTH_TYPE_CLOUD,
    DEFAULT_TIME_RANGE,
    DEFAULT_UPDATE_INTERVAL,
    TIME_RANGES,
)

_LOGGER = logging.getLogger(__name__)


class UmamiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Umami Analytics."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._client: UmamiApiClient | None = None
        self._data: dict[str, Any] = {}
        self._websites: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the auth step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            auth_type = user_input[CONF_AUTH_TYPE]
            url = user_input[CONF_URL].rstrip("/")

            session = async_get_clientsession(self.hass)

            try:
                if auth_type == AUTH_TYPE_CLOUD:
                    self._client = UmamiApiClient(
                        url=url,
                        api_key=user_input[CONF_API_KEY],
                        session=session,
                    )
                else:
                    self._client = UmamiApiClient(
                        url=url,
                        username=user_input[CONF_USERNAME],
                        password=user_input[CONF_PASSWORD],
                        session=session,
                    )

                await self._client.validate_connection()
                self._websites = await self._client.get_websites()

            except UmamiAuthError:
                errors["base"] = "invalid_auth"
                self._client = None
            except UmamiConnectionError:
                errors["base"] = "cannot_connect"
                self._client = None
            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
                self._client = None
            else:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()

                self._data = user_input
                self._data[CONF_URL] = url
                return await self.async_step_sites()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                    vol.Required(CONF_AUTH_TYPE, default=AUTH_TYPE_SELF_HOSTED): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": AUTH_TYPE_SELF_HOSTED, "label": "Self-hosted (Username/Password)"},
                                {"value": AUTH_TYPE_CLOUD, "label": "Umami Cloud (API Key)"},
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                    vol.Optional(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_sites(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle site selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = user_input.get(CONF_SITES, [])
            if not selected:
                errors["base"] = "no_sites_selected"
            else:
                self._data[CONF_SITES] = selected

                title = f"Umami ({self._data[CONF_URL].split('//')[1].split('/')[0]})"
                return self.async_create_entry(
                    title=title,
                    data=self._data,
                    options={
                        CONF_TIME_RANGE: DEFAULT_TIME_RANGE,
                        CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
                    },
                )

        site_options = [
            {"value": site["id"], "label": f"{site['name']} ({site['domain']})"}
            for site in self._websites
        ]

        return self.async_show_form(
            step_id="sites",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SITES): SelectSelector(
                        SelectSelectorConfig(
                            options=site_options,
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> UmamiOptionsFlow:
        """Get the options flow."""
        return UmamiOptionsFlow(config_entry)


class UmamiOptionsFlow(OptionsFlow):
    """Handle options for Umami Analytics."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options step."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        time_range_options = [
            {"value": k, "label": v} for k, v in TIME_RANGES.items()
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TIME_RANGE,
                        default=self._config_entry.options.get(
                            CONF_TIME_RANGE, DEFAULT_TIME_RANGE
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=time_range_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=self._config_entry.options.get(
                            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            max=60,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="min",
                        )
                    ),
                }
            ),
        )
