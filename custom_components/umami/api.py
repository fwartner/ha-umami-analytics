"""Umami Analytics API client."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class UmamiApiError(Exception):
    """Base exception for Umami API errors."""


class UmamiAuthError(UmamiApiError):
    """Authentication error."""


class UmamiConnectionError(UmamiApiError):
    """Connection error."""


class UmamiApiClient:
    """Client for Umami Analytics API v2."""

    def __init__(
        self,
        url: str,
        *,
        username: str | None = None,
        password: str | None = None,
        api_key: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the API client."""
        self._url = url.rstrip("/")
        self._username = username
        self._password = password
        self._api_key = api_key
        self._token: str | None = None
        self._session = session
        self._owns_session = session is None

    @property
    def is_cloud(self) -> bool:
        """Return True if using cloud API key auth."""
        return self._api_key is not None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the HTTP session if we own it."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def _authenticate(self) -> None:
        """Authenticate with Umami (self-hosted only)."""
        if self.is_cloud:
            return

        session = await self._get_session()
        try:
            resp = await session.post(
                f"{self._url}/api/auth/login",
                json={"username": self._username, "password": self._password},
            )
        except aiohttp.ClientError as err:
            raise UmamiConnectionError(f"Cannot connect to {self._url}") from err

        if resp.status == 401:
            raise UmamiAuthError("Invalid username or password")
        if resp.status != 200:
            raise UmamiApiError(f"Auth failed with status {resp.status}")

        data = await resp.json()
        self._token = data.get("token")
        if not self._token:
            raise UmamiAuthError("No token in auth response")

    def _headers(self) -> dict[str, str]:
        """Return authorization headers."""
        token = self._api_key if self.is_cloud else self._token
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Make an authenticated API request with auto-retry on 401."""
        session = await self._get_session()
        url = f"{self._url}{path}"

        if not self.is_cloud and not self._token:
            await self._authenticate()

        try:
            resp = await session.request(
                method, url, headers=self._headers(), **kwargs
            )
        except aiohttp.ClientError as err:
            raise UmamiConnectionError(f"Cannot connect to {self._url}") from err

        if resp.status == 401 and not self.is_cloud:
            await self._authenticate()
            try:
                resp = await session.request(
                    method, url, headers=self._headers(), **kwargs
                )
            except aiohttp.ClientError as err:
                raise UmamiConnectionError(
                    f"Cannot connect to {self._url}"
                ) from err

        if resp.status == 401:
            raise UmamiAuthError("Authentication failed")
        if resp.status != 200:
            raise UmamiApiError(f"API request failed: {resp.status}")

        return await resp.json()

    async def validate_connection(self) -> bool:
        """Validate the connection and credentials."""
        if self.is_cloud:
            await self._request("GET", "/api/websites", params={"pageSize": "1"})
        else:
            await self._authenticate()
        return True

    async def get_websites(self) -> list[dict[str, Any]]:
        """Fetch all websites from Umami, including team websites.

        Paginates through all results and includes team-owned sites.
        """
        all_sites: list[dict[str, Any]] = []
        page = 1
        page_size = 100

        while True:
            result = await self._request(
                "GET",
                "/api/websites",
                params={
                    "includeTeams": "true",
                    "pageSize": str(page_size),
                    "page": str(page),
                },
            )

            if isinstance(result, dict) and "data" in result:
                sites = result["data"]
                all_sites.extend(sites)
                # Stop if we got fewer than requested (last page)
                if len(sites) < page_size:
                    break
                page += 1
            elif isinstance(result, list):
                # Older Umami versions return a plain list
                all_sites.extend(result)
                break
            else:
                break

        return all_sites

    async def get_stats(
        self, website_id: str, time_range: str = "today"
    ) -> dict[str, Any]:
        """Fetch stats for a website."""
        start, end = self._time_range_to_timestamps(time_range)
        result = await self._request(
            "GET",
            f"/api/websites/{website_id}/stats",
            params={"startAt": str(start), "endAt": str(end)},
        )
        return result if isinstance(result, dict) else {}

    async def get_active(self, website_id: str) -> int:
        """Fetch active visitors for a website."""
        result = await self._request(
            "GET", f"/api/websites/{website_id}/active"
        )
        return result.get("visitors", 0) if isinstance(result, dict) else 0

    async def get_metrics(
        self,
        website_id: str,
        metric_type: str,
        time_range: str = "today",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch metrics (pages, referrers, browsers, etc.) for a website."""
        start, end = self._time_range_to_timestamps(time_range)
        result = await self._request(
            "GET",
            f"/api/websites/{website_id}/metrics",
            params={
                "startAt": str(start),
                "endAt": str(end),
                "type": metric_type,
                "limit": str(limit),
            },
        )
        return result if isinstance(result, list) else []

    async def get_events_count(
        self, website_id: str, time_range: str = "today"
    ) -> int:
        """Fetch total event count for a website."""
        start, end = self._time_range_to_timestamps(time_range)
        result = await self._request(
            "GET",
            f"/api/websites/{website_id}/metrics",
            params={
                "startAt": str(start),
                "endAt": str(end),
                "type": "event",
            },
        )
        if isinstance(result, list):
            return sum(item.get("y", item.get("visitors", 0)) for item in result)
        return 0

    @staticmethod
    def _time_range_to_timestamps(time_range: str) -> tuple[int, int]:
        """Convert time range string to start/end millisecond timestamps."""
        now = datetime.now(timezone.utc)
        end = int(now.timestamp() * 1000)

        if time_range == "24h":
            start = end - (24 * 60 * 60 * 1000)
        elif time_range == "7d":
            start = end - (7 * 24 * 60 * 60 * 1000)
        elif time_range == "30d":
            start = end - (30 * 24 * 60 * 60 * 1000)
        elif time_range == "month":
            start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            start = int(start_dt.timestamp() * 1000)
        else:  # today
            start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
            start = int(start_dt.timestamp() * 1000)

        return start, end
