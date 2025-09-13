#!/usr/bin/env python3
"""
Quick test to verify the API is working
"""

import httpx
import asyncio
import sys

async def quick_test():
    """Run a quick test of the API"""
    
    # Test without API key (should work for health)
    print("Testing health endpoint...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:8000/health")
            if response.status_code == 200:
                print("✅ Health check passed!")
                print(f"   Response: {response.json()}")
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Cannot connect to API: {e}")
            print("\n💡 To start the API, run:")
            print("   cd /Users/keylongjasper/Documents/shopify监控/shopify-monitor-backend")
            print("   python -m uvicorn app.main:app --reload")
            return False
    
    # Test with API key
    print("\nTesting authenticated endpoint...")
    headers = {"X-API-Key": "test-api-key-123"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:8000/api/v1/dashboard", headers=headers)
            if response.status_code == 200:
                print("✅ Dashboard endpoint passed!")
                data = response.json()
                print(f"   Total stores: {data.get('total_stores', 0)}")
            else:
                print(f"❌ Dashboard failed: {response.status_code}")
                if response.status_code == 403:
                    print("   Check your API key in .env file")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    # Test quick scan
    print("\nTesting quick scan (this may take 10-30 seconds)...")
    payload = {
        "store_url": "https://yoyosquishy.com",
        "use_proxy": None,
        "save_results": False
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                "http://localhost:8000/api/v1/scan",
                json=payload,
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                print("✅ Quick scan successful!")
                print(f"   Products found: {data['statistics']['total_products']}")
                print(f"   Total stock: {data['statistics']['total_stock']}")
                print(f"   Scan time: {data['scan_duration']:.2f}s")
            else:
                print(f"⚠️  Scan returned status: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
        except Exception as e:
            print(f"❌ Scan error: {e}")
    
    print("\n✨ Quick test completed!")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Shopify Monitor API - Quick Test")
    print("=" * 60)
    
    result = asyncio.run(quick_test())
    sys.exit(0 if result else 1)