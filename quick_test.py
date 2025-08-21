#!/usr/bin/env python3
"""
Quick DMI API Test
Simple test to check if the API is working
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta

# Configuration
API_KEY = "2f0562a7-8444-4889-9ef4-1f0e3a62f609"
LATITUDE = 55.9667
LONGITUDE = 12.7667

async def quick_test():
    """Quick test of the DMI API."""
    print("🚀 Quick DMI API Test")
    print("=" * 40)
    
    # Test collections endpoint
    print("1. Testing collections endpoint...")
    url = "https://dmigw.govcloud.dk/v1/forecastedr/collections"
    headers = {"X-Gravitee-Api-Key": API_KEY}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                print(f"   Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    collections = data.get("collections", [])
                    print(f"   ✅ Found {len(collections)} collections")
                    for coll in collections[:3]:  # Show first 3
                        print(f"   - {coll['id']}")
                else:
                    print(f"   ❌ Error: {response.status}")
                    return False
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False
    
    # Test weather data endpoint
    print("\n2. Testing weather data endpoint...")
    now = datetime.utcnow()
    end_time = now + timedelta(hours=24)  # 24 hours from now
    
    weather_url = f"https://dmigw.govcloud.dk/v1/forecastedr/collections/harmonie_dini_eps_means/position"
    params = {
        "coords": f"POINT({LONGITUDE} {LATITUDE})",
        "datetime": f"{now.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end_time.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "parameter-name": "temperature-2m",
        "f": "CoverageJSON"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(weather_url, params=params, headers=headers) as response:
                print(f"   Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    if "ranges" in data and "temperature-2m" in data["ranges"]:
                        temp_data = data["ranges"]["temperature-2m"]
                        if "values" in temp_data and temp_data["values"]:
                            temp_k = temp_data["values"][0]
                            temp_c = temp_k - 273.15 if temp_k > 200 else temp_k
                            print(f"   ✅ Got temperature data: {temp_c:.1f}°C")
                        else:
                            print("   ⚠️  No temperature values found")
                    else:
                        print("   ⚠️  No temperature data in response")
                else:
                    error_text = await response.text()
                    print(f"   ❌ Error: {response.status} - {error_text}")
                    return False
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False
    
    print("\n✅ Quick test completed successfully!")
    return True

if __name__ == "__main__":
    asyncio.run(quick_test())
