"""DMI Weather EDR API client."""
from __future__ import annotations

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import (
    DMI_EDR_BASE_URL, DMI_AUTH_HEADER, EDR_COLLECTIONS_ENDPOINT,
    EDR_POSITION_QUERY, DEFAULT_TIMEOUT, EDR_PARAMETERS, MAX_FORECAST_DAYS
)

_LOGGER = logging.getLogger(__name__)

class DMIWeatherAPI:
    """DMI Weather API client with Docker DNS fallback."""
    
    def __init__(self, hass: HomeAssistant, latitude: float, longitude: float, api_key: str) -> None:
        self.hass = hass
        self.latitude = latitude
        self.longitude = longitude
        self.api_key = api_key
        self.current_data: Dict[str, Any] = {}
        self.hourly_forecast_data: List[Dict[str, Any]] = []
        self.forecast_data: List[Dict[str, Any]] = []
        self._last_request_time = 0
        self._rate_limit_delay = 5.0
        self._max_retries = 3
        
        # Use only the domain name - Home Assistant's HTTP client handles DNS
        self._api_urls = [
            DMI_EDR_BASE_URL,  # Original domain
        ]

    async def _rate_limit(self) -> None:
        """Ensure minimum delay between API requests to avoid rate limiting."""
        now = asyncio.get_event_loop().time()
        time_since_last = now - self._last_request_time
        if time_since_last < self._rate_limit_delay:
            delay = self._rate_limit_delay - time_since_last
            await asyncio.sleep(delay)
        self._last_request_time = asyncio.get_event_loop().time()

    async def _make_request(self, endpoint: str, params: Dict = None) -> Dict[str, Any]:
        """Make API request using Home Assistant's HTTP client."""
        headers = {DMI_AUTH_HEADER: self.api_key}
        
        # Use Home Assistant's built-in HTTP client
        session = async_get_clientsession(self.hass)
        
        # Use the domain URL
        url = f"{self._api_urls[0]}{endpoint}"
        _LOGGER.debug("Making request to: %s", url)
        
        try:
            async with session.get(url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT) as response:
                if response.status == 429:
                    _LOGGER.warning("Rate limit exceeded, waiting before retry")
                    await asyncio.sleep(10)
                    raise Exception("Rate limit exceeded, please try again later")
                elif response.status == 404:
                    error_text = await response.text()
                    _LOGGER.error("API returned 404: %s", error_text)
                    raise Exception("No weather data available for the requested time period. Please try again later.")
                elif response.status != 200:
                    error_text = await response.text()
                    _LOGGER.error("API request failed with status %d: %s", response.status, error_text)
                    raise Exception(f"API request failed with status {response.status}")
                
                data = await response.json()
                _LOGGER.debug("Successfully connected to DMI API")
                return data
                    
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout connecting to DMI EDR API")
            raise Exception("Timeout connecting to DMI EDR API. Please try again.")
        except Exception as e:
            _LOGGER.error("Error connecting to DMI EDR API: %s", e)
            raise Exception(f"Network error: {e}")

    async def test_connection(self) -> bool:
        """Test API connection without affecting rate limits."""
        try:
            await self._rate_limit()
            collections = await self._get_collections()
            return len(collections) > 0
        except Exception as e:
            _LOGGER.error("Connection test failed: %s", e)
            return False

    async def update(self) -> None:
        """Update weather data from DMI EDR API."""
        for attempt in range(self._max_retries):
            try:
                await self._rate_limit()
                collections = await self._get_collections()
                if not collections:
                    raise Exception("No EDR collections available")

                collection_id = "harmonie_dini_eps_means"
                if collection_id not in collections:
                    collection_id = list(collections.keys())[0]
                _LOGGER.debug("Using EDR collection: %s", collection_id)

                await self._fetch_weather_data(collection_id)
                return  # Success
            except Exception as err:
                _LOGGER.warning("Attempt %d/%d failed: %s", attempt + 1, self._max_retries, err)
                if attempt < self._max_retries - 1:
                    wait_time = (2 ** attempt) * 2
                    _LOGGER.info("Waiting %d seconds before retry...", wait_time)
                    await asyncio.sleep(wait_time)
                else:
                    _LOGGER.error("All %d attempts failed. Last error: %s", self._max_retries, err)
                    raise

    async def _get_collections(self) -> Dict[str, Any]:
        """Get available EDR collections."""
        await self._rate_limit()
        data = await self._make_request(EDR_COLLECTIONS_ENDPOINT)
        
        # Process collections data
        collections = {}
        if "collections" in data:
            for collection in data["collections"]:
                collections[collection["id"]] = collection
        
        return collections

    async def _fetch_weather_data(self, collection_id: str) -> Dict[str, Any]:
        """Fetch weather data from DMI EDR API."""
        await self._rate_limit()
        
        now = dt_util.utcnow()
        end_time = now + timedelta(days=MAX_FORECAST_DAYS)
        start_time_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        _LOGGER.debug("Requesting weather data from %s to %s", start_time_str, end_time_str)

        essential_params = [
            "temperature-2m", "wind-speed-10m", "gust-wind-speed-10m",
            "total-precipitation", "fraction-of-cloud-cover", "dew-point-temperature-2m"
        ]
        params = {
            "coords": f"POINT({self.longitude} {self.latitude})",
            "datetime": f"{start_time_str}/{end_time_str}",
            "parameter-name": ",".join(essential_params),
            "f": "CoverageJSON"
        }

        endpoint = f"{EDR_COLLECTIONS_ENDPOINT}/{collection_id}{EDR_POSITION_QUERY}"
        data = await self._make_request(endpoint, params)
        await self._process_edr_data(data)

    def _process_edr_data(self, data: Dict[str, Any]) -> None:
        """Process the CoverageJSON data from EDR API."""
        if not data or "ranges" not in data:
            _LOGGER.error("No weather data received from DMI EDR API")
            return

        ranges = data["ranges"]
        domain = data.get("domain", {})
        axes = domain.get("axes", {})
        
        # Extract time axis
        time_values = axes.get("t", {}).get("values", [])
        if not time_values:
            _LOGGER.error("No time values in EDR response")
            return

        _LOGGER.debug("Processing %d time steps", len(time_values))
        
        # Process hourly data
        hourly_data = []
        
        for i, time_str in enumerate(time_values):
            try:
                # Parse time
                time_obj = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                
                # Extract weather values for this time step
                weather_data = {
                    "time": time_obj,
                    "temperature": self._extract_parameter_value(ranges, EDR_PARAMETERS["temperature"], i),
                    "pressure": None,  # Set to None if not requested
                    "humidity": None,  # Set to None if not requested
                    "wind_speed": self._extract_parameter_value(ranges, EDR_PARAMETERS["wind_speed"], i),
                    "wind_gust": self._extract_parameter_value(ranges, EDR_PARAMETERS["wind_gust"], i),
                    "precipitation": self._extract_parameter_value(ranges, EDR_PARAMETERS["precipitation"], i),
                    "cloud_cover": self._extract_parameter_value(ranges, EDR_PARAMETERS["cloud_cover"], i),
                    "dew_point": self._extract_parameter_value(ranges, EDR_PARAMETERS["dew_point"], i),
                    "weather_code": None,
                }
                
                # Estimate weather condition based on precipitation and cloud cover
                if weather_data["precipitation"] and weather_data["precipitation"] > 0.1:
                    weather_data["weather_code"] = "rainy"
                elif weather_data["cloud_cover"] and weather_data["cloud_cover"] > 80:
                    weather_data["weather_code"] = "cloudy"
                elif weather_data["cloud_cover"] and weather_data["cloud_cover"] > 30:
                    weather_data["weather_code"] = "partlycloudy"
                else:
                    weather_data["weather_code"] = "clear"
                
                hourly_data.append(weather_data)
                    
            except (ValueError, TypeError) as err:
                _LOGGER.warning("Error parsing data at index %d: %s", i, err)
                continue

        # Set current data to the first time step
        if hourly_data:
            self.current_data = hourly_data[0].copy()
            self.hourly_forecast_data = hourly_data[1:25]  # Next 24 hours
            self.forecast_data = hourly_data[1:]  # All future data

    def _extract_parameter_value(self, ranges: Dict, parameter: str, time_index: int) -> Optional[float]:
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
        if parameter == "temperature-2m" and value > 200:
            value = value - 273.15
        
        # Convert dew point from Kelvin to Celsius if needed
        if parameter == "dew-point-temperature-2m" and value > 200:
            value = value - 273.15
        
        # Convert cloud cover from fraction to percentage if needed
        if parameter == "fraction-of-cloud-cover" and value <= 1:
            value = value * 100
        
        return float(value)
