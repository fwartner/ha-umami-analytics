"""Umami Analytics integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import UmamiApiClient, UmamiAuthError, UmamiConnectionError
from .const import (
    DOMAIN,
    CONF_URL,
    CONF_AUTH_TYPE,
    CONF_API_KEY,
    AUTH_TYPE_CLOUD,
)
from .coordinator import UmamiCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Umami Analytics from a config entry."""
    url = entry.data[CONF_URL]
    auth_type = entry.data.get(CONF_AUTH_TYPE)
    session = async_get_clientsession(hass)

    if auth_type == AUTH_TYPE_CLOUD:
        client = UmamiApiClient(
            url=url, api_key=entry.data[CONF_API_KEY], session=session
        )
    else:
        client = UmamiApiClient(
            url=url,
            username=entry.data.get(CONF_USERNAME),
            password=entry.data.get(CONF_PASSWORD),
            session=session,
        )

    try:
        await client.validate_connection()
    except UmamiAuthError as err:
        raise ConfigEntryAuthFailed from err
    except UmamiConnectionError as err:
        raise ConfigEntryNotReady from err

    coordinator = UmamiCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update — reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)
