# Umami Analytics for Home Assistant

[![GitHub Release](https://img.shields.io/github/release/fwartner/ha-umami-analytics.svg?style=flat-square)](https://github.com/fwartner/ha-umami-analytics/releases)
[![License](https://img.shields.io/github/license/fwartner/ha-umami-analytics.svg?style=flat-square)](LICENSE)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square)](https://github.com/hacs/integration)
[![Validate](https://github.com/fwartner/ha-umami-analytics/actions/workflows/validate.yml/badge.svg)](https://github.com/fwartner/ha-umami-analytics/actions/workflows/validate.yml)

Monitor your [Umami Analytics](https://umami.is) website statistics directly in Home Assistant.

Supports both **self-hosted Umami** instances and **Umami Cloud**.

---

## Features

- **Dual authentication** — Self-hosted (username/password) or Umami Cloud (API key)
- **Site selection** — Choose which websites to monitor during setup
- **7 sensors per site** — Pageviews, visitors, visits, bounces, avg visit time, active users, events
- **Rich attributes** — Top 10 pages, referrers, browsers, and countries on the pageviews sensor
- **Configurable** — Time range (today / 24h / 7d / 30d / this month) and update interval (1–60 min)
- **Device grouping** — Each website appears as a device with all its sensors
- **Translations** — English and German included

## Installation

### HACS (Recommended)

1. Open [HACS](https://hacs.xyz/) in Home Assistant
2. Click the **three dots** in the top right corner and select **Custom repositories**
3. Add `https://github.com/fwartner/ha-umami-analytics` with category **Integration**
4. Search for **Umami Analytics** and click **Download**
5. Restart Home Assistant

### Manual

1. Download the [latest release](https://github.com/fwartner/ha-umami-analytics/releases/latest)
2. Extract and copy the `custom_components/umami` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Setup

1. Go to **Settings** > **Devices & Services** > **Add Integration**
2. Search for **Umami Analytics**
3. Enter your Umami instance URL (e.g. `https://analytics.example.com`)
4. Select your authentication method:
   - **Self-hosted**: Enter your Umami username and password
   - **Umami Cloud**: Enter your API key
5. Select which websites to monitor
6. Done! Sensors will appear under the new Umami device(s)

## Sensors

For each selected website, the following sensors are created:

| Sensor | Description | Unit |
|--------|-------------|------|
| **Pageviews** | Total page views in the selected time range | pageviews |
| **Visitors** | Unique visitors | visitors |
| **Visits** | Total sessions | visits |
| **Bounces** | Single-page visits | bounces |
| **Avg Visit Time** | Average session duration | seconds |
| **Active Users** | Currently active visitors (realtime) | users |
| **Events** | Custom events tracked | events |

### Extra Attributes

The **Pageviews** sensor includes extra state attributes:

- `top_pages` — Top 10 most visited pages
- `top_referrers` — Top 10 traffic sources
- `top_browsers` — Top 10 browsers
- `top_countries` — Top 10 visitor countries

These can be used in templates, automations, or Lovelace cards.

## Options

After setup, configure the integration via **Settings** > **Devices & Services** > **Umami Analytics** > **Configure**:

| Option | Default | Description |
|--------|---------|-------------|
| Time range | Today | Period for stats: Today, Last 24h, Last 7 days, Last 30 days, This month |
| Update interval | 5 min | How often to poll the Umami API (1–60 minutes) |

## Compatibility

| Component | Version |
|-----------|---------|
| Home Assistant | 2024.1.0 or newer |
| Umami | v2.x API |
| HACS | 2.0.0 or newer |

## Troubleshooting

**"Invalid authentication" error during setup**
- Self-hosted: Verify your username and password work on the Umami web UI
- Cloud: Ensure your API key is valid and has not expired

**"Cannot connect" error during setup**
- Verify the URL is reachable from your Home Assistant instance
- Ensure you include the protocol (`https://`)
- Check that no firewall or reverse proxy is blocking the connection

**Sensors show "unavailable"**
- Check Home Assistant logs for errors from the `umami` integration
- Verify the Umami instance is online and the API is responding

## Contributing

Contributions are welcome! Please open an [issue](https://github.com/fwartner/ha-umami-analytics/issues) or submit a pull request.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
