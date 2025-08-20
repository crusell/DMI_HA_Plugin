"""Support for DMI Weather EDR."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, cast

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .const import (
    CONF_LATITUDE as CONF_LAT,
    CONF_LONGITUDE as CONF_LON,
    CONF_API_KEY,
    DEFAULT_NAME,
    DOMAIN,
    WEATHER_CONDITIONS,
)
from .dmi_edr_api import DMIWeatherEDRAPI

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DMI Weather EDR weather platform."""
    name = config_entry.data[CONF_NAME]
    latitude = config_entry.data[CONF_LATITUDE]
    longitude = config_entry.data[CONF_LONGITUDE]
    api_key = config_entry.data[CONF_API_KEY]

    api = DMIWeatherEDRAPI(hass, latitude, longitude, api_key)
    
    async_add_entities([DMIWeatherEDREntity(name, api)], True)


class DMIWeatherEDREntity(WeatherEntity):
    """Representation of a DMI Weather EDR entity."""

    _attr_attribution = "Data provided by Danish Meteorological Institute (DMI) via EDR API"
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_visibility_unit = UnitOfLength.KILOMETERS
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_supported_features = WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY

    def __init__(self, name: str, api: DMIWeatherEDRAPI) -> None:
        """Initialize the DMI Weather EDR entity."""
        self._api = api
        self._attr_name = name
        self._attr_unique_id = f"dmi_edr_{api.latitude}_{api.longitude}"

    async def async_update(self) -> None:
        """Update current weather data."""
        try:
            await self._api.update()
            self._attr_available = True
        except Exception as err:
            _LOGGER.error("Error updating DMI EDR weather: %s", err)
            self._attr_available = False

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        if not self._api.current_data:
            return None
        
        # Map DMI weather codes to Home Assistant conditions
        weather_code = self._api.current_data.get("weather_code")
        if weather_code is not None:
            return WEATHER_CONDITIONS.get(str(weather_code), "unknown")
        
        return None

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        if not self._api.current_data:
            return None
        return self._api.current_data.get("temperature")

    @property
    def native_pressure(self) -> float | None:
        """Return the pressure."""
        if not self._api.current_data:
            return None
        return self._api.current_data.get("pressure")

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        if not self._api.current_data:
            return None
        return self._api.current_data.get("wind_speed")

    @property
    def wind_bearing(self) -> float | None:
        """Return the wind bearing."""
        if not self._api.current_data:
            return None
        return self._api.current_data.get("wind_direction")

    @property
    def native_visibility(self) -> float | None:
        """Return the visibility."""
        if not self._api.current_data:
            return None
        visibility = self._api.current_data.get("visibility")
        if visibility is not None:
            return visibility / 1000  # Convert to km
        return None

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        if not self._api.current_data:
            return None
        return self._api.current_data.get("humidity")

    @property
    def native_wind_gust_speed(self) -> float | None:
        """Return the wind gust speed."""
        if not self._api.current_data:
            return None
        return self._api.current_data.get("wind_gust")

    @property
    def cloud_coverage(self) -> float | None:
        """Return the cloud coverage."""
        if not self._api.current_data:
            return None
        return self._api.current_data.get("cloud_cover")

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast."""
        if not self._api.forecast_data:
            return None

        forecast_list = []
        for forecast in self._api.forecast_data:
            forecast_dict = {
                ATTR_FORECAST_TIME: forecast.get("time"),
                ATTR_FORECAST_NATIVE_TEMP: forecast.get("temperature_max"),
                ATTR_FORECAST_NATIVE_TEMP_LOW: forecast.get("temperature_min"),
                ATTR_FORECAST_NATIVE_PRECIPITATION: forecast.get("precipitation"),
                ATTR_FORECAST_WIND_SPEED: forecast.get("wind_speed"),
                ATTR_FORECAST_WIND_BEARING: forecast.get("wind_direction"),
            }
            
            # Map weather condition
            weather_code = forecast.get("weather_code")
            if weather_code is not None:
                forecast_dict[ATTR_FORECAST_CONDITION] = WEATHER_CONDITIONS.get(
                    str(weather_code), "unknown"
                )
            
            forecast_list.append(Forecast(**forecast_dict))

        return forecast_list

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast."""
        if not self._api.hourly_forecast_data:
            return None

        forecast_list = []
        for forecast in self._api.hourly_forecast_data:
            forecast_dict = {
                ATTR_FORECAST_TIME: forecast.get("time"),
                ATTR_FORECAST_NATIVE_TEMP: forecast.get("temperature"),
                ATTR_FORECAST_NATIVE_PRECIPITATION: forecast.get("precipitation"),
                ATTR_FORECAST_WIND_SPEED: forecast.get("wind_speed"),
                ATTR_FORECAST_WIND_BEARING: forecast.get("wind_direction"),
            }
            
            # Map weather condition
            weather_code = forecast.get("weather_code")
            if weather_code is not None:
                forecast_dict[ATTR_FORECAST_CONDITION] = WEATHER_CONDITIONS.get(
                    str(weather_code), "unknown"
                )
            
            forecast_list.append(Forecast(**forecast_dict))

        return forecast_list
