"""DMI Weather EDR API client."""
from __future__ import annotations

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from aiohttp import ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    DMI_EDR_BASE_URL,
    DMI_AUTH_HEADER,
    EDR_COLLECTIONS_ENDPOINT,
    EDR_POSITION_QUERY,
    DEFAULT_TIMEOUT,
    MAX_FORECAST_DAYS,
    EDR_PARAMETERS,
)

_LOGGER = logging.getLogger(__name__)


class DMIWeatherAPI:
    """DMI Weather API client."""

    def __init__(self, hass: HomeAssistant, latitude: float, longitude: float, api_key: str) -> None:
        """Initialize the DMI Weather API client."""
        self.hass = hass
        self.latitude = latitude
        self.longitude = longitude
        self.api_key = api_key
        self.current_data: dict[str, Any] = {}
        self.forecast_data: list[dict[str, Any]] = []
        self.hourly_forecast_data: list[dict[str, Any]] = []
        self._last_request_time = 0
        self._rate_limit_delay = 2.0  # Minimum 2 seconds between requests

    async def _rate_limit(self) -> None:
        """Ensure minimum delay between API requests to avoid rate limiting."""
        now = asyncio.get_event_loop().time()
        time_since_last = now - self._last_request_time
        if time_since_last < self._rate_limit_delay:
            delay = self._rate_limit_delay - time_since_last
            await asyncio.sleep(delay)
        self._last_request_time = asyncio.get_event_loop().time()

    async def update(self) -> None:
        """Update weather data from DMI EDR API."""
        try:
            # Apply rate limiting
            await self._rate_limit()
            
            # Get available collections first
            collections = await self._get_collections()
            if not collections:
                raise Exception("No EDR collections available")
            
            # Use the HARMONIE DINI EPS means collection for weather data
            collection_id = "harmonie_dini_eps_means"
            if collection_id not in collections:
                # Fallback to first available collection
                collection_id = list(collections.keys())[0]
            _LOGGER.debug("Using EDR collection: %s", collection_id)
            
            # Get current weather and forecast
            await self._fetch_weather_data(collection_id)
        except Exception as err:
            _LOGGER.error("Error fetching DMI EDR weather data: %s", err)
            raise

    async def _get_collections(self) -> dict[str, Any]:
        """Get available EDR collections."""
        await self._rate_limit()
        url = f"{DMI_EDR_BASE_URL}{EDR_COLLECTIONS_ENDPOINT}"
        headers = {DMI_AUTH_HEADER: self.api_key}
        
        try:
            timeout = ClientTimeout(total=DEFAULT_TIMEOUT, connect=10, sock_read=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 429:
                        _LOGGER.warning("Rate limit exceeded, waiting before retry")
                        await asyncio.sleep(5)  # Wait 5 seconds before retry
                        raise Exception("Rate limit exceeded, please try again later")
                    elif response.status != 200:
                        raise Exception(f"Collections API request failed with status {response.status}")
                    
                    data = await response.json()
                    collections = {}
                    
                    if "collections" in data:
                        for collection in data["collections"]:
                            collections[collection["id"]] = collection
                    
                    return collections
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout connecting to DMI EDR API")
            raise Exception("Timeout connecting to DMI EDR API. Please try again.")
        except aiohttp.ClientError as e:
            _LOGGER.error("Network error connecting to DMI EDR API: %s", e)
            raise Exception(f"Network error: {e}")

    async def _fetch_weather_data(self, collection_id: str) -> None:
        """Fetch weather data from DMI EDR API."""
        await self._rate_limit()
        # Build position query URL
        url = f"{DMI_EDR_BASE_URL}{EDR_COLLECTIONS_ENDPOINT}/{collection_id}{EDR_POSITION_QUERY}"
        headers = {DMI_AUTH_HEADER: self.api_key}
        
        # Calculate time range for forecast
        now = dt_util.now()
        end_time = now + timedelta(days=MAX_FORECAST_DAYS)
        
        # Format times for EDR API (ISO 8601)
        start_time_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        _LOGGER.debug("Requesting weather data from %s to %s", start_time_str, end_time_str)
        
        # Build query parameters for position query
        params = {
            "coords": f"POINT({self.longitude} {self.latitude})",
            "datetime": f"{start_time_str}/{end_time_str}",
            "parameter-name": ",".join(EDR_PARAMETERS.values()),
            "f": "CoverageJSON"  # Request CoverageJSON format
        }
        
        try:
            timeout = ClientTimeout(total=DEFAULT_TIMEOUT, connect=10, sock_read=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 429:
                        _LOGGER.warning("Rate limit exceeded, waiting before retry")
                        await asyncio.sleep(5)  # Wait 5 seconds before retry
                        raise Exception("Rate limit exceeded, please try again later")
                    elif response.status == 404:
                        error_text = await response.text()
                        _LOGGER.error("EDR position query returned 404: %s", error_text)
                        raise Exception("No weather data available for the requested time period. Please try again later.")
                    elif response.status != 200:
                        error_text = await response.text()
                        _LOGGER.error("EDR position query failed with status %d: %s", response.status, error_text)
                        raise Exception(f"EDR position query failed with status {response.status}")
                    
                    data = await response.json()
                    await self._process_edr_data(data)
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout connecting to DMI EDR API")
            raise Exception("Timeout connecting to DMI EDR API. Please try again.")
        except aiohttp.ClientError as e:
            _LOGGER.error("Network error connecting to DMI EDR API: %s", e)
            raise Exception(f"Network error: {e}")

    async def _process_edr_data(self, data: dict[str, Any]) -> None:
        """Process weather data from EDR API response."""
        if not data or "ranges" not in data:
            _LOGGER.warning("No weather data received from DMI EDR API")
            return

        ranges = data["ranges"]
        domain = data.get("domain", {})
        axes = domain.get("axes", {})
        
        # Extract time axis
        time_values = axes.get("t", {}).get("values", [])
        if not time_values:
            _LOGGER.warning("No time values in EDR response")
            return

        # Process hourly data
        hourly_data = []
        current_data = {}
        
        for i, time_str in enumerate(time_values):
            try:
                # Parse time
                time_obj = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                
                # Extract weather values for this time step
                weather_data = {
                    "time": time_obj,
                    "temperature": self._extract_parameter_value(ranges, "temperature-2m", i),
                    "pressure": self._extract_parameter_value(ranges, "pressure-sealevel", i),
                    "humidity": self._extract_parameter_value(ranges, "relative-humidity-2m", i),
                    "wind_speed": self._extract_parameter_value(ranges, "wind-speed-10m", i),
                    "wind_gust": self._extract_parameter_value(ranges, "gust-wind-speed-10m", i),
                    "precipitation": self._extract_parameter_value(ranges, "total-precipitation", i),
                    "cloud_cover": self._extract_parameter_value(ranges, "fraction-of-cloud-cover", i),
                    "dew_point": self._extract_parameter_value(ranges, "dew-point-temperature-2m", i),
                    "weather_code": None,  # Will be estimated from other parameters
                }
                
                # Estimate weather code
                weather_data["weather_code"] = self._estimate_weather_code(
                    weather_data.get("precipitation"),
                    weather_data.get("cloud_cover")
                )
                
                hourly_data.append(weather_data)
                
                # Use first hour as current weather
                if i == 0:
                    current_data = weather_data.copy()
                    
            except (ValueError, TypeError) as err:
                _LOGGER.warning("Error parsing EDR weather data at index %d: %s", i, err)
                continue

        self.hourly_forecast_data = hourly_data
        self.current_data = current_data
        
        # Create daily forecast from hourly data
        self._create_daily_forecast(hourly_data)

    def _extract_parameter_value(self, ranges: dict, parameter: str, time_index: int) -> float | None:
        """Extract parameter value from EDR ranges data."""
        if parameter not in ranges:
            return None
        
        param_data = ranges[parameter]
        if "values" not in param_data:
            return None
        
        values = param_data["values"]
        if time_index >= len(values):
            return None
        
        value = values[time_index]
        if value is None:
            return None
        
        # Convert temperature from Kelvin to Celsius if needed
        if parameter == "temperature-2m" and value > 200:  # Likely Kelvin
            value = value - 273.15
        
        # Convert pressure from Pa to hPa if needed
        if parameter == "pressure-sealevel" and value > 10000:  # Likely Pa
            value = value / 100
        
        # Convert cloud cover from fraction to percentage if needed
        if parameter == "fraction-of-cloud-cover" and value <= 1:
            value = value * 100
        
        # Convert dew point from Kelvin to Celsius if needed
        if parameter == "dew-point-temperature-2m" and value > 200:  # Likely Kelvin
            value = value - 273.15
        
        return float(value)

    def _estimate_weather_code(self, precipitation: float | None, cloud_cover: float | None) -> int:
        """Estimate weather code based on available data."""
        if precipitation and precipitation > 0.1:
            return 3  # Rain
        elif cloud_cover and cloud_cover > 80:
            return 2  # Cloudy
        elif cloud_cover and cloud_cover > 30:
            return 1  # Partly cloudy
        else:
            return 0  # Clear

    def _create_daily_forecast(self, hourly_data: list[dict[str, Any]]) -> None:
        """Create daily forecast from hourly data."""
        daily_forecast = []
        
        # Group by day
        current_date = None
        daily_data = {}
        
        for hour_data in hourly_data:
            time_obj = hour_data.get("time")
            if not time_obj:
                continue
            
            date_key = time_obj.date()
            
            if date_key != current_date:
                if current_date and daily_data:
                    daily_forecast.append(daily_data)
                current_date = date_key
                daily_data = {
                    "time": time_obj,
                    "temperature_max": float("-inf"),
                    "temperature_min": float("inf"),
                    "precipitation": 0.0,
                    "wind_speed": 0.0,
                    "wind_direction": 0.0,
                    "weather_code": None,
                }
            
            # Update daily data
            temp = hour_data.get("temperature")
            if temp is not None:
                daily_data["temperature_max"] = max(daily_data["temperature_max"], temp)
                daily_data["temperature_min"] = min(daily_data["temperature_min"], temp)
            
            precip = hour_data.get("precipitation")
            if precip is not None:
                daily_data["precipitation"] += precip
            
            wind_speed = hour_data.get("wind_speed")
            if wind_speed is not None:
                daily_data["wind_speed"] = wind_speed
            
            wind_dir = hour_data.get("wind_direction")
            if wind_dir is not None:
                daily_data["wind_direction"] = wind_dir
            
            weather_code = hour_data.get("weather_code")
            if weather_code is not None:
                daily_data["weather_code"] = weather_code
        
        # Add last day
        if current_date and daily_data:
            daily_forecast.append(daily_data)
        
        # Clean up temperature values
        for day_data in daily_forecast:
            if day_data["temperature_max"] == float("-inf"):
                day_data["temperature_max"] = None
            if day_data["temperature_min"] == float("inf"):
                day_data["temperature_min"] = None
        
        self.forecast_data = daily_forecast
