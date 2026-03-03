"""Umami Analytics integration for Home Assistant."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import UmamiApiClient, UmamiAuthError, UmamiConnectionError
from .const import (
    DOMAIN,
    CONF_URL,
    CONF_AUTH_TYPE,
    CONF_API_KEY,
    CONF_SITES,
    AUTH_TYPE_CLOUD,
    TIME_RANGES,
)
from .coordinator import UmamiCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

SERVICE_REFRESH = "refresh"
SERVICE_GET_STATS = "get_stats"
SERVICE_TRACK_EVENT = "track_event"


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

    # Register services (only once, on first entry)
    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        _register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    # Unregister services if no entries remain
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
        hass.services.async_remove(DOMAIN, SERVICE_GET_STATS)
        hass.services.async_remove(DOMAIN, SERVICE_TRACK_EVENT)

    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update — reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)


def _get_coordinators(hass: HomeAssistant) -> list[UmamiCoordinator]:
    """Get all active Umami coordinators."""
    return list(hass.data.get(DOMAIN, {}).values())


def _get_coordinator_for_site(
    hass: HomeAssistant, site_id: str
) -> UmamiCoordinator | None:
    """Find the coordinator that manages a specific site."""
    for coordinator in _get_coordinators(hass):
        if site_id in coordinator.config_entry.data.get(CONF_SITES, []):
            return coordinator
    return None


def _register_services(hass: HomeAssistant) -> None:
    """Register Umami service actions."""

    async def handle_refresh(call: ServiceCall) -> None:
        """Handle the refresh service call — force update all coordinators."""
        for coordinator in _get_coordinators(hass):
            await coordinator.async_request_refresh()
        _LOGGER.debug("Umami data refresh requested for all entries")

    async def handle_get_stats(call: ServiceCall) -> ServiceResponse:
        """Handle the get_stats service call — return stats for all sites."""
        time_range = call.data.get("time_range")
        results: dict[str, Any] = {}

        for coordinator in _get_coordinators(hass):
            site_ids = coordinator.config_entry.data.get(CONF_SITES, [])
            for site_id in site_ids:
                try:
                    stats = await coordinator.async_get_site_stats(
                        site_id, time_range
                    )
                    meta = coordinator._site_meta.get(site_id, {})
                    site_name = meta.get("name", site_id)
                    results[site_name] = stats
                except Exception:
                    _LOGGER.warning(
                        "Failed to fetch stats for site %s", site_id
                    )

        return {"sites": results}

    async def handle_track_event(call: ServiceCall) -> None:
        """Handle the track_event service call — send an event to Umami."""
        website_id = call.data["website_id"]
        event_name = call.data["event_name"]
        url_path = call.data.get("url", "/")
        referrer = call.data.get("referrer", "")
        event_data = call.data.get("data")

        coordinator = _get_coordinator_for_site(hass, website_id)
        if coordinator is None:
            # Use the first available coordinator's client
            coordinators = _get_coordinators(hass)
            if not coordinators:
                _LOGGER.error("No Umami integration configured")
                return
            coordinator = coordinators[0]

        await coordinator.client.send_event(
            website_id=website_id,
            event_name=event_name,
            url_path=url_path,
            referrer=referrer,
            data=event_data,
        )
        _LOGGER.debug(
            "Sent event '%s' to site %s", event_name, website_id
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        handle_refresh,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_STATS,
        handle_get_stats,
        schema=vol.Schema(
            {
                vol.Optional("time_range"): vol.In(list(TIME_RANGES.keys())),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TRACK_EVENT,
        handle_track_event,
        schema=vol.Schema(
            {
                vol.Required("website_id"): str,
                vol.Required("event_name"): str,
                vol.Optional("url", default="/"): str,
                vol.Optional("referrer", default=""): str,
                vol.Optional("data"): dict,
            }
        ),
    )
