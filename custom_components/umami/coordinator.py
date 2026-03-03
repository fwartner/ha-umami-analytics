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

    # Core stats from /stats endpoint
    pageviews: int = 0
    visitors: int = 0
    visits: int = 0
    bounces: int = 0
    totaltime: int = 0

    # Realtime
    active_users: int = 0

    # Events
    events: int = 0

    # Metric breakdowns (top 10 each)
    top_pages: list[dict[str, Any]] = field(default_factory=list)
    top_entry_pages: list[dict[str, Any]] = field(default_factory=list)
    top_exit_pages: list[dict[str, Any]] = field(default_factory=list)
    top_referrers: list[dict[str, Any]] = field(default_factory=list)
    top_channels: list[dict[str, Any]] = field(default_factory=list)
    top_browsers: list[dict[str, Any]] = field(default_factory=list)
    top_os: list[dict[str, Any]] = field(default_factory=list)
    top_devices: list[dict[str, Any]] = field(default_factory=list)
    top_countries: list[dict[str, Any]] = field(default_factory=list)
    top_regions: list[dict[str, Any]] = field(default_factory=list)
    top_cities: list[dict[str, Any]] = field(default_factory=list)
    top_languages: list[dict[str, Any]] = field(default_factory=list)
    top_screens: list[dict[str, Any]] = field(default_factory=list)
    top_events: list[dict[str, Any]] = field(default_factory=list)
    top_titles: list[dict[str, Any]] = field(default_factory=list)

    @property
    def avg_visit_time(self) -> float:
        """Calculate average visit time in seconds."""
        if self.visits == 0:
            return 0.0
        return round(self.totaltime / self.visits, 1)

    @property
    def bounce_rate(self) -> float:
        """Calculate bounce rate as a percentage."""
        if self.visits == 0:
            return 0.0
        return round((self.bounces / self.visits) * 100, 1)

    @property
    def views_per_visit(self) -> float:
        """Calculate average pageviews per visit."""
        if self.visits == 0:
            return 0.0
        return round(self.pageviews / self.visits, 1)


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

    async def async_get_site_stats(
        self, site_id: str, time_range: str | None = None
    ) -> dict[str, Any]:
        """Fetch stats for a specific site with an optional time range override.

        Used by the get_stats service action. Returns raw stats dict.
        """
        tr = time_range or self._time_range
        stats = await self.client.get_stats(site_id, tr)
        active = await self.client.get_active(site_id)
        events = await self.client.get_events_count(site_id, tr)

        return {
            "site_id": site_id,
            "time_range": tr,
            "pageviews": self._extract_stat(stats, "pageviews"),
            "visitors": self._extract_stat(stats, "visitors"),
            "visits": self._extract_stat(stats, "visits"),
            "bounces": self._extract_stat(stats, "bounces"),
            "totaltime": self._extract_stat(stats, "totaltime"),
            "active_users": active,
            "events": events,
        }

    async def _fetch_site_data(
        self, site_id: str, meta: dict[str, str]
    ) -> UmamiSiteData:
        """Fetch all data for a single site."""
        stats = await self.client.get_stats(site_id, self._time_range)
        active = await self.client.get_active(site_id)
        events = await self.client.get_events_count(site_id, self._time_range)

        # Fetch all metric dimensions (top 10 each)
        tr = self._time_range
        get = self.client.get_metrics

        top_pages = await get(site_id, "path", tr, limit=10)
        top_entry_pages = await get(site_id, "entry", tr, limit=10)
        top_exit_pages = await get(site_id, "exit", tr, limit=10)
        top_referrers = await get(site_id, "referrer", tr, limit=10)
        top_channels = await get(site_id, "channel", tr, limit=10)
        top_browsers = await get(site_id, "browser", tr, limit=10)
        top_os = await get(site_id, "os", tr, limit=10)
        top_devices = await get(site_id, "device", tr, limit=10)
        top_countries = await get(site_id, "country", tr, limit=10)
        top_regions = await get(site_id, "region", tr, limit=10)
        top_cities = await get(site_id, "city", tr, limit=10)
        top_languages = await get(site_id, "language", tr, limit=10)
        top_screens = await get(site_id, "screen", tr, limit=10)
        top_events = await get(site_id, "event", tr, limit=10)
        top_titles = await get(site_id, "title", tr, limit=10)

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
            top_entry_pages=top_entry_pages,
            top_exit_pages=top_exit_pages,
            top_referrers=top_referrers,
            top_channels=top_channels,
            top_browsers=top_browsers,
            top_os=top_os,
            top_devices=top_devices,
            top_countries=top_countries,
            top_regions=top_regions,
            top_cities=top_cities,
            top_languages=top_languages,
            top_screens=top_screens,
            top_events=top_events,
            top_titles=top_titles,
        )
