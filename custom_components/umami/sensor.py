"""Sensor platform for Umami Analytics."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_TYPES, CONF_URL
from .coordinator import UmamiCoordinator, UmamiSiteData

_LOGGER = logging.getLogger(__name__)


def _slugify_domain(domain: str) -> str:
    """Convert domain to a slug for entity IDs."""
    return re.sub(r"[^a-z0-9]+", "_", domain.lower()).strip("_")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Umami sensors from a config entry."""
    coordinator: UmamiCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[UmamiSensor] = []
    for site_id, site_data in coordinator.data.items():
        for sensor_type in SENSOR_TYPES:
            entities.append(
                UmamiSensor(coordinator, entry, site_id, site_data, sensor_type)
            )

    async_add_entities(entities)


class UmamiSensor(CoordinatorEntity[UmamiCoordinator], SensorEntity):
    """Representation of an Umami Analytics sensor."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: UmamiCoordinator,
        entry: ConfigEntry,
        site_id: str,
        site_data: UmamiSiteData,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._site_id = site_id
        self._sensor_type = sensor_type
        self._domain_slug = _slugify_domain(site_data.domain)

        sensor_info = SENSOR_TYPES[sensor_type]
        self._attr_name = sensor_info["name"]
        self._attr_icon = sensor_info["icon"]
        self._attr_native_unit_of_measurement = sensor_info["unit"]
        self._attr_unique_id = f"{entry.entry_id}_{site_id}_{sensor_type}"

        instance_url = entry.data.get(CONF_URL, "")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{site_id}")},
            name=f"Umami: {site_data.name}",
            manufacturer="Umami Analytics",
            model=site_data.domain,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"{instance_url}/websites/{site_id}",
        )

    @property
    def _site_data(self) -> UmamiSiteData | None:
        """Get current site data from coordinator."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._site_id)

    @property
    def available(self) -> bool:
        """Return True if site data is available."""
        return super().available and self._site_data is not None

    @property
    def native_value(self) -> int | float | None:
        """Return the sensor value."""
        site = self._site_data
        if site is None:
            return None

        if self._sensor_type == "avg_visit_time":
            return site.avg_visit_time

        return getattr(site, self._sensor_type, None)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes for the pageviews sensor."""
        if self._sensor_type != "pageviews":
            return None

        site = self._site_data
        if site is None:
            return None

        return {
            "top_pages": site.top_pages[:10],
            "top_referrers": site.top_referrers[:10],
            "top_browsers": site.top_browsers[:10],
            "top_countries": site.top_countries[:10],
        }
