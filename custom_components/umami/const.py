"""Constants for the Umami Analytics integration."""

DOMAIN = "umami"

CONF_URL = "url"
CONF_AUTH_TYPE = "auth_type"
CONF_API_KEY = "api_key"
CONF_SITES = "sites"
CONF_TIME_RANGE = "time_range"
CONF_UPDATE_INTERVAL = "update_interval"

AUTH_TYPE_SELF_HOSTED = "self_hosted"
AUTH_TYPE_CLOUD = "cloud"

DEFAULT_UPDATE_INTERVAL = 5  # minutes
DEFAULT_TIME_RANGE = "today"

TIME_RANGES = {
    "today": "Today",
    "24h": "Last 24 hours",
    "7d": "Last 7 days",
    "30d": "Last 30 days",
    "month": "This month",
}

SENSOR_TYPES = {
    "pageviews": {
        "name": "Pageviews",
        "icon": "mdi:eye",
        "unit": "pageviews",
    },
    "visitors": {
        "name": "Visitors",
        "icon": "mdi:account-group",
        "unit": "visitors",
    },
    "visits": {
        "name": "Visits",
        "icon": "mdi:login",
        "unit": "visits",
    },
    "bounces": {
        "name": "Bounces",
        "icon": "mdi:arrow-u-left-top",
        "unit": "bounces",
    },
    "bounce_rate": {
        "name": "Bounce Rate",
        "icon": "mdi:percent",
        "unit": "%",
    },
    "avg_visit_time": {
        "name": "Avg Visit Time",
        "icon": "mdi:clock-outline",
        "unit": "s",
    },
    "views_per_visit": {
        "name": "Views Per Visit",
        "icon": "mdi:book-open-page-variant",
        "unit": "pages",
    },
    "active_users": {
        "name": "Active Users",
        "icon": "mdi:account-clock",
        "unit": "users",
    },
    "events": {
        "name": "Events",
        "icon": "mdi:bell-ring",
        "unit": "events",
    },
}
