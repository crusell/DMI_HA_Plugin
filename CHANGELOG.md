# Changelog

All notable changes to the DMI Weather integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-08-20

### Added
- Initial release of DMI Weather EDR integration
- Support for current weather conditions
- 24-hour hourly forecasts
- 5-day daily forecasts
- GPS coordinate-based location support
- API key authentication
- Comprehensive weather parameters:
  - Temperature (current, high/low)
  - Wind speed and gust
  - Precipitation
  - Cloud cover
  - Humidity
  - Pressure
  - Weather conditions
- Fast EDR API integration (2-3 second response times)
- Efficient data transfer (10KB vs 7GB GRIB files)
- Complete Home Assistant integration structure
- Configuration flow with validation
- Error handling and logging
- Documentation and examples

### Technical Features
- Uses DMI EDR (Environmental Data Retrieval) API
- HARMONIE DINI EPS means weather model
- CoverageJSON data format
- Cloud polling architecture
- Automatic updates every 15 minutes
- Metric units (Celsius, m/s, hPa, mm)

---

## [Unreleased]

### Planned
- Additional weather parameters
- Extended forecast periods
- Multiple location support
- Advanced configuration options
