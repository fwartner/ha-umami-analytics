"""DataUpdateCoordinator for Umami Analytics."""

from __future__ import annotations

from datetime import timedelta
import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import UmamiApiClient, UmamiAuthError, UmamiApiError
from .const import (
    DOMAIN,
    CONF_SITES,
    CONF_TIME_RANGE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_TIME_RANGE,
    DEFAULT_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class UmamiSiteData:
    """Data for a single Umami site."""

    site_id: str
    name: str
    domain: str
    pageviews: int = 0
    visitors: int = 0
    visits: int = 0
    bounces: int = 0
    totaltime: int = 0
    active_users: int = 0
    events: int = 0
    top_pages: list[dict[str, Any]] = field(default_factory=list)
    top_referrers: list[dict[str, Any]] = field(default_factory=list)
    top_browsers: list[dict[str, Any]] = field(default_factory=list)
    top_countries: list[dict[str, Any]] = field(default_factory=list)

    @property
    def avg_visit_time(self) -> float:
        """Calculate average visit time in seconds."""
        if self.visits == 0:
            return 0.0
        return round(self.totaltime / self.visits, 1)


class UmamiCoordinator(DataUpdateCoordinator[dict[str, UmamiSiteData]]):
    """Coordinator to fetch Umami data for all selected sites."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: UmamiApiClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self._site_ids: list[str] = config_entry.data.get(CONF_SITES, [])
        self._time_range: str = config_entry.options.get(
            CONF_TIME_RANGE, DEFAULT_TIME_RANGE
        )
        self._site_meta: dict[str, dict[str, str]] = {}

        interval = int(
            config_entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=interval),
            config_entry=config_entry,
        )

    async def _async_setup(self) -> None:
        """Fetch website metadata on first run."""
        try:
            websites = await self.client.get_websites()
        except UmamiAuthError as err:
            raise ConfigEntryAuthFailed from err
        except UmamiApiError as err:
            raise UpdateFailed(f"Error fetching websites: {err}") from err

        for site in websites:
            self._site_meta[site["id"]] = {
                "name": site.get("name", "Unknown"),
                "domain": site.get("domain", "unknown"),
            }

    @staticmethod
    def _extract_stat(stats: dict[str, Any], key: str) -> int:
        """Extract a stat value, handling both plain ints and nested dicts."""
        val = stats.get(key, 0)
        if isinstance(val, dict):
            return val.get("value", 0)
        return val

    async def _async_update_data(self) -> dict[str, UmamiSiteData]:
        """Fetch data for all selected sites."""
        data: dict[str, UmamiSiteData] = {}

        for site_id in self._site_ids:
            meta = self._site_meta.get(site_id, {})
            if not meta:
                _LOGGER.warning("Site %s not found in Umami, skipping", site_id)
                continue

            try:
                site_data = await self._fetch_site_data(site_id, meta)
                data[site_id] = site_data
            except UmamiAuthError as err:
                raise ConfigEntryAuthFailed from err
            except UmamiApiError as err:
                _LOGGER.warning(
                    "Error fetching data for %s: %s", meta.get("name"), err
                )
                if self.data and site_id in self.data:
                    data[site_id] = self.data[site_id]

        return data

    async def _fetch_site_data(
        self, site_id: str, meta: dict[str, str]
    ) -> UmamiSiteData:
        """Fetch all data for a single site."""
        stats = await self.client.get_stats(site_id, self._time_range)
        active = await self.client.get_active(site_id)
        events = await self.client.get_events_count(site_id, self._time_range)

        top_pages = await self.client.get_metrics(
            site_id, "url", self._time_range, limit=10
        )
        top_referrers = await self.client.get_metrics(
            site_id, "referrer", self._time_range, limit=10
        )
        top_browsers = await self.client.get_metrics(
            site_id, "browser", self._time_range, limit=10
        )
        top_countries = await self.client.get_metrics(
            site_id, "country", self._time_range, limit=10
        )

        return UmamiSiteData(
            site_id=site_id,
            name=meta["name"],
            domain=meta["domain"],
            pageviews=self._extract_stat(stats, "pageviews"),
            visitors=self._extract_stat(stats, "visitors"),
            visits=self._extract_stat(stats, "visits"),
            bounces=self._extract_stat(stats, "bounces"),
            totaltime=self._extract_stat(stats, "totaltime"),
            active_users=active,
            events=events,
            top_pages=top_pages,
            top_referrers=top_referrers,
            top_browsers=top_browsers,
            top_countries=top_countries,
        )
