#!/usr/bin/env python3
"""
Standalone DMI Weather API Test (Rate-Limited Version)
Tests the DMI EDR API integration with proper rate limiting
"""

import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Reduced logging level
    format='%(asctime)s - %(levelname)s - %(message)s'
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

class SlowDMITester:
    """DMI API tester with proper rate limiting."""
    
    def __init__(self, latitude: float, longitude: float, api_key: str):
        self.latitude = latitude
        self.longitude = longitude
        self.api_key = api_key
        self._last_request_time = 0
        self._rate_limit_delay = 10.0  # 10 seconds between requests
        self._max_retries = 2

    async def _rate_limit(self) -> None:
        """Ensure minimum delay between API requests."""
        now = asyncio.get_event_loop().time()
        time_since_last = now - self._last_request_time
        if time_since_last < self._rate_limit_delay:
            delay = self._rate_limit_delay - time_since_last
            print(f"⏳ Rate limiting: waiting {delay:.1f} seconds...")
            await asyncio.sleep(delay)
        self._last_request_time = asyncio.get_event_loop().time()

    async def _make_request(self, url: str, params: Dict = None) -> Dict[str, Any]:
        """Make a single API request with proper error handling."""
        headers = {DMI_AUTH_HEADER: self.api_key}
        
        try:
            timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT, connect=10, sock_read=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params, headers=headers) as response:
                    print(f"📡 API Status: {response.status}")
                    
                    if response.status == 429:
                        print("⚠️  Rate limit exceeded, waiting 15 seconds...")
                        await asyncio.sleep(15)
                        raise Exception("Rate limit exceeded")
                    elif response.status == 404:
                        error_text = await response.text()
                        print(f"❌ 404 Error: {error_text}")
                        raise Exception("No data available for the requested time period")
                    elif response.status != 200:
                        error_text = await response.text()
                        print(f"❌ API Error: {error_text}")
                        raise Exception(f"API failed with status {response.status}")
                    
                    return await response.json()
        except asyncio.TimeoutError:
            print("⏰ Timeout connecting to DMI EDR API")
            raise Exception("Timeout connecting to DMI EDR API")
        except aiohttp.ClientError as e:
            print(f"🌐 Network error: {e}")
            raise Exception(f"Network error: {e}")

    async def test_connection(self) -> bool:
        """Test API connection."""
        try:
            print("🔗 Testing API connection...")
            await self._rate_limit()
            
            url = f"{DMI_EDR_BASE_URL}{EDR_COLLECTIONS_ENDPOINT}"
            data = await self._make_request(url)
            
            collections = {}
            if "collections" in data:
                for collection in data["collections"]:
                    collections[collection["id"]] = collection
            
            print(f"✅ Found {len(collections)} collections")
            for collection_id in list(collections.keys())[:5]:  # Show first 5
                print(f"   - {collection_id}")
            
            return True
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            return False

    async def test_weather_data(self) -> bool:
        """Test weather data retrieval."""
        try:
            print("\n🌤️  Testing weather data retrieval...")
            
            # Get collections first
            await self._rate_limit()
            url = f"{DMI_EDR_BASE_URL}{EDR_COLLECTIONS_ENDPOINT}"
            data = await self._make_request(url)
            
            collections = {}
            if "collections" in data:
                for collection in data["collections"]:
                    collections[collection["id"]] = collection
            
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
            await self._rate_limit()
            weather_url = f"{DMI_EDR_BASE_URL}{EDR_COLLECTIONS_ENDPOINT}/{collection_id}{EDR_POSITION_QUERY}"
            
            # Calculate time range for forecast
            now = datetime.utcnow()
            end_time = now + timedelta(days=2)  # Reduced to 2 days
            
            params = {
                "coords": f"POINT({self.longitude} {self.latitude})",
                "datetime": f"{now.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end_time.strftime('%Y-%m-%dT%H:%M:%SZ')}",
                "parameter-name": ",".join(ESSENTIAL_PARAMS),
                "f": "CoverageJSON"
            }
            
            print(f"📅 Requesting data from {now.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}")
            
            data = await self._make_request(weather_url, params)
            
            # Process the data
            if not data or "ranges" not in data:
                print("❌ No weather data received")
                return False

            ranges = data["ranges"]
            domain = data.get("domain", {})
            axes = domain.get("axes", {})
            time_values = axes.get("t", {}).get("values", [])
            
            if not time_values:
                print("❌ No time values in response")
                return False

            print(f"✅ Successfully retrieved {len(time_values)} time steps")
            
            # Show sample data
            print("\n📊 Sample Weather Data:")
            print("Time                 | Temp | Wind | Gust | Rain | Cloud")
            print("-" * 65)
            
            for i, time_str in enumerate(time_values[:4]):  # Show first 4 hours
                try:
                    time_obj = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                    time_str = time_obj.strftime("%Y-%m-%d %H:%M")
                    
                    # Extract values
                    temp = ranges.get("temperature-2m", {}).get("values", [None])[i]
                    wind = ranges.get("wind-speed-10m", {}).get("values", [None])[i]
                    gust = ranges.get("gust-wind-speed-10m", {}).get("values", [None])[i]
                    rain = ranges.get("total-precipitation", {}).get("values", [None])[i]
                    cloud = ranges.get("fraction-of-cloud-cover", {}).get("values", [None])[i]
                    
                    # Convert units
                    if temp and temp > 200:
                        temp = temp - 273.15
                    if cloud and cloud <= 1:
                        cloud = cloud * 100
                    
                    # Format output
                    temp_str = f"{temp:.1f}°C" if temp is not None else "N/A"
                    wind_str = f"{wind:.1f}" if wind is not None else "N/A"
                    gust_str = f"{gust:.1f}" if gust is not None else "N/A"
                    rain_str = f"{rain:.2f}" if rain is not None else "0.00"
                    cloud_str = f"{cloud:.0f}%" if cloud is not None else "N/A"
                    
                    print(f"{time_str} | {temp_str:>5} | {wind_str:>4} | {gust_str:>4} | {rain_str:>4} | {cloud_str:>5}")
                    
                except (ValueError, TypeError, IndexError) as err:
                    print(f"Error parsing data at index {i}: {err}")
                    continue
            
            return True
                
        except Exception as e:
            print(f"❌ Weather data test failed: {e}")
            return False

    async def run_full_test(self) -> None:
        """Run complete test suite."""
        print("=" * 60)
        print("🌤️  DMI Weather API Test (Rate-Limited)")
        print("=" * 60)
        print(f"📍 Location: {LATITUDE}, {LONGITUDE}")
        print(f"🔑 API Key: {API_KEY[:8]}...")
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏳ Rate limit: {self._rate_limit_delay} seconds between requests")
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
    tester = SlowDMITester(LATITUDE, LONGITUDE, API_KEY)
    await tester.run_full_test()

if __name__ == "__main__":
    asyncio.run(main())
