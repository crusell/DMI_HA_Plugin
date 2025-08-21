#!/usr/bin/env python3
"""
Standalone DMI Weather API Test
Tests the DMI EDR API integration without Home Assistant
"""

import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
_LOGGER = logging.getLogger(__name__)

# Configuration
API_KEY = "2f0562a7-8444-4889-9ef4-1f0e3a62f609"
LATITUDE = 55.9667
LONGITUDE = 12.7667
DMI_EDR_BASE_URL = "https://dmigw.govcloud.dk/v1/forecastedr"
DMI_AUTH_HEADER = "X-Gravitee-Api-Key"
EDR_COLLECTIONS_ENDPOINT = "/collections"
EDR_POSITION_QUERY = "/position"
DEFAULT_TIMEOUT = 60

# Essential weather parameters
ESSENTIAL_PARAMS = [
    "temperature-2m",
    "wind-speed-10m", 
    "gust-wind-speed-10m",
    "total-precipitation",
    "fraction-of-cloud-cover"
]

class StandaloneDMITester:
    """Standalone DMI API tester without Home Assistant dependencies."""
    
    def __init__(self, latitude: float, longitude: float, api_key: str):
        self.latitude = latitude
        self.longitude = longitude
        self.api_key = api_key
        self._last_request_time = 0
        self._rate_limit_delay = 5.0
        self._max_retries = 3

    async def _rate_limit(self) -> None:
        """Ensure minimum delay between API requests."""
        now = asyncio.get_event_loop().time()
        time_since_last = now - self._last_request_time
        if time_since_last < self._rate_limit_delay:
            delay = self._rate_limit_delay - time_since_last
            print(f"Rate limiting: waiting {delay:.1f} seconds...")
            await asyncio.sleep(delay)
        self._last_request_time = asyncio.get_event_loop().time()

    async def _get_collections(self) -> Dict[str, Any]:
        """Get available EDR collections."""
        await self._rate_limit()
        url = f"{DMI_EDR_BASE_URL}{EDR_COLLECTIONS_ENDPOINT}"
        headers = {DMI_AUTH_HEADER: self.api_key}
        
        try:
            timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT, connect=10, sock_read=30)
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, ttl_dns_cache=300)
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.get(url, headers=headers) as response:
                    print(f"Collections API Status: {response.status}")
                    
                    if response.status == 429:
                        print("Rate limit exceeded, waiting 10 seconds...")
                        await asyncio.sleep(10)
                        raise Exception("Rate limit exceeded")
                    elif response.status != 200:
                        error_text = await response.text()
                        print(f"Collections API Error: {error_text}")
                        raise Exception(f"Collections API failed with status {response.status}")
                    
                    data = await response.json()
                    collections = {}
                    
                    if "collections" in data:
                        for collection in data["collections"]:
                            collections[collection["id"]] = collection
                    
                    return collections
        except asyncio.TimeoutError:
            print("Timeout connecting to DMI EDR API")
            raise Exception("Timeout connecting to DMI EDR API")
        except aiohttp.ClientError as e:
            print(f"Network error: {e}")
            raise Exception(f"Network error: {e}")

    async def _fetch_weather_data(self, collection_id: str) -> Dict[str, Any]:
        """Fetch weather data from DMI EDR API."""
        await self._rate_limit()
        url = f"{DMI_EDR_BASE_URL}{EDR_COLLECTIONS_ENDPOINT}/{collection_id}{EDR_POSITION_QUERY}"
        headers = {DMI_AUTH_HEADER: self.api_key}
        
        # Calculate time range for forecast
        now = datetime.utcnow()
        end_time = now + timedelta(days=5)
        
        # Format times for EDR API (ISO 8601)
        start_time_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        print(f"Requesting weather data from {start_time_str} to {end_time_str}")
        
        params = {
            "coords": f"POINT({self.longitude} {self.latitude})",
            "datetime": f"{start_time_str}/{end_time_str}",
            "parameter-name": ",".join(ESSENTIAL_PARAMS),
            "f": "CoverageJSON"
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT, connect=10, sock_read=30)
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, ttl_dns_cache=300)
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.get(url, params=params, headers=headers) as response:
                    print(f"Weather API Status: {response.status}")
                    
                    if response.status == 429:
                        print("Rate limit exceeded, waiting 10 seconds...")
                        await asyncio.sleep(10)
                        raise Exception("Rate limit exceeded")
                    elif response.status == 404:
                        error_text = await response.text()
                        print(f"404 Error: {error_text}")
                        raise Exception("No weather data available for the requested time period")
                    elif response.status != 200:
                        error_text = await response.text()
                        print(f"Weather API Error: {error_text}")
                        raise Exception(f"Weather API failed with status {response.status}")
                    
                    data = await response.json()
                    return data
        except asyncio.TimeoutError:
            print("Timeout connecting to DMI EDR API")
            raise Exception("Timeout connecting to DMI EDR API")
        except aiohttp.ClientError as e:
            print(f"Network error: {e}")
            raise Exception(f"Network error: {e}")

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
        
        # Convert cloud cover from fraction to percentage if needed
        if parameter == "fraction-of-cloud-cover" and value <= 1:
            value = value * 100
        
        return float(value)

    def _estimate_weather_code(self, precipitation: Optional[float], cloud_cover: Optional[float]) -> str:
        """Estimate weather code based on available data."""
        if precipitation and precipitation > 0.1:
            return "Rain"
        elif cloud_cover and cloud_cover > 80:
            return "Cloudy"
        elif cloud_cover and cloud_cover > 30:
            return "Partly Cloudy"
        else:
            return "Clear"

    def _process_weather_data(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process weather data from EDR API response."""
        if not data or "ranges" not in data:
            print("No weather data received from DMI EDR API")
            return []

        ranges = data["ranges"]
        domain = data.get("domain", {})
        axes = domain.get("axes", {})
        
        # Extract time axis
        time_values = axes.get("t", {}).get("values", [])
        if not time_values:
            print("No time values in EDR response")
            return []

        print(f"Processing {len(time_values)} time steps...")
        
        # Process hourly data
        hourly_data = []
        
        for i, time_str in enumerate(time_values):
            try:
                # Parse time
                time_obj = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                
                # Extract weather values for this time step
                weather_data = {
                    "time": time_obj,
                    "temperature": self._extract_parameter_value(ranges, "temperature-2m", i),
                    "wind_speed": self._extract_parameter_value(ranges, "wind-speed-10m", i),
                    "wind_gust": self._extract_parameter_value(ranges, "gust-wind-speed-10m", i),
                    "precipitation": self._extract_parameter_value(ranges, "total-precipitation", i),
                    "cloud_cover": self._extract_parameter_value(ranges, "fraction-of-cloud-cover", i),
                }
                
                # Estimate weather code
                weather_data["condition"] = self._estimate_weather_code(
                    weather_data.get("precipitation"),
                    weather_data.get("cloud_cover")
                )
                
                hourly_data.append(weather_data)
                    
            except (ValueError, TypeError) as err:
                print(f"Error parsing data at index {i}: {err}")
                continue

        return hourly_data

    async def test_connection(self) -> bool:
        """Test API connection."""
        try:
            print("Testing API connection...")
            collections = await self._get_collections()
            print(f"✅ Found {len(collections)} collections:")
            for collection_id in collections:
                print(f"  - {collection_id}")
            return True
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            return False

    async def test_weather_data(self) -> bool:
        """Test weather data retrieval."""
        try:
            print("\nTesting weather data retrieval...")
            
            # Get collections first
            collections = await self._get_collections()
            if not collections:
                print("❌ No collections available")
                return False
            
            # Use the HARMONIE DINI EPS means collection
            collection_id = "harmonie_dini_eps_means"
            if collection_id not in collections:
                collection_id = list(collections.keys())[0]
                print(f"⚠️  Using fallback collection: {collection_id}")
            else:
                print(f"✅ Using collection: {collection_id}")
            
            # Fetch weather data
            data = await self._fetch_weather_data(collection_id)
            
            # Process the data
            hourly_data = self._process_weather_data(data)
            
            if hourly_data:
                print(f"✅ Successfully retrieved {len(hourly_data)} hourly forecasts")
                
                # Show first few forecasts
                print("\n📊 Sample Forecast Data:")
                print("Time                 | Temp | Wind | Gust | Rain | Cloud | Condition")
                print("-" * 75)
                for i, forecast in enumerate(hourly_data[:6]):  # Show first 6 hours
                    time_str = forecast["time"].strftime("%Y-%m-%d %H:%M")
                    temp = f"{forecast['temperature']:.1f}°C" if forecast['temperature'] is not None else "N/A"
                    wind = f"{forecast['wind_speed']:.1f}" if forecast['wind_speed'] is not None else "N/A"
                    gust = f"{forecast['wind_gust']:.1f}" if forecast['wind_gust'] is not None else "N/A"
                    rain = f"{forecast['precipitation']:.2f}" if forecast['precipitation'] is not None else "0.00"
                    cloud = f"{forecast['cloud_cover']:.0f}%" if forecast['cloud_cover'] is not None else "N/A"
                    condition = forecast.get('condition', 'Unknown')
                    
                    print(f"{time_str} | {temp:>5} | {wind:>4} | {gust:>4} | {rain:>4} | {cloud:>5} | {condition}")
                
                return True
            else:
                print("❌ No weather data processed")
                return False
                
        except Exception as e:
            print(f"❌ Weather data test failed: {e}")
            return False

    async def run_full_test(self) -> None:
        """Run complete test suite."""
        print("=" * 60)
        print("🌤️  DMI Weather API Standalone Test")
        print("=" * 60)
        print(f"Location: {LATITUDE}, {LONGITUDE}")
        print(f"API Key: {API_KEY[:8]}...")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Test 1: Connection
        connection_ok = await self.test_connection()
        
        if connection_ok:
            # Test 2: Weather Data
            weather_ok = await self.test_weather_data()
            
            if weather_ok:
                print("\n🎉 All tests passed! The DMI API integration is working correctly.")
            else:
                print("\n❌ Weather data test failed.")
        else:
            print("\n❌ Connection test failed.")
        
        print("\n" + "=" * 60)

async def main():
    """Main function."""
    tester = StandaloneDMITester(LATITUDE, LONGITUDE, API_KEY)
    await tester.run_full_test()

if __name__ == "__main__":
    asyncio.run(main())
