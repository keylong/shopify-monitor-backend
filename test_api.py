#!/usr/bin/env python3
"""
API Test Script for Shopify Monitor
"""

import httpx
import asyncio
import json
from datetime import datetime
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"
API_KEY = "test-api-key-123"
TEST_STORE_URL = "https://yoyosquishy.com"


class APITester:
    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"X-API-Key": API_KEY},
            timeout=30.0
        )
        self.store_id = None
        
    async def test_health(self):
        """Test health endpoint"""
        print("\n🔍 Testing health endpoint...")
        response = await self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Health check passed: {data}")
        return data
        
    async def test_quick_scan(self):
        """Test quick scan endpoint"""
        print(f"\n🔍 Testing quick scan for {TEST_STORE_URL}...")
        payload = {
            "store_url": TEST_STORE_URL,
            "use_proxy": None,
            "save_results": True
        }
        
        response = await self.client.post("/api/v1/scan", json=payload)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Quick scan successful!")
            print(f"   - Products found: {data['statistics']['total_products']}")
            print(f"   - Valid variants: {data['statistics']['valid_variants']}")
            print(f"   - Total stock: {data['statistics']['total_stock']}")
            print(f"   - Scan duration: {data['scan_duration']:.2f}s")
            return data
        else:
            print(f"❌ Quick scan failed: {response.status_code} - {response.text}")
            return None
            
    async def test_dashboard(self):
        """Test dashboard stats endpoint"""
        print("\n🔍 Testing dashboard stats...")
        response = await self.client.get("/api/v1/dashboard")
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Dashboard stats retrieved:")
        print(f"   - Total stores: {data['total_stores']}")
        print(f"   - Active stores: {data['active_stores']}")
        print(f"   - Total products: {data['total_products']}")
        print(f"   - Recent scans: {data['recent_scans']}")
        return data
        
    async def test_store_crud(self):
        """Test store CRUD operations"""
        print("\n🔍 Testing store CRUD operations...")
        
        # Create store
        print("   Creating store...")
        store_data = {
            "name": "Test Store - YoYo Squishy",
            "url": TEST_STORE_URL,
            "description": "Test store for API validation",
            "scan_interval": 3600,
            "enabled": True,
            "notify_low_stock": True,
            "low_stock_threshold": 10
        }
        
        response = await self.client.post("/api/v1/stores/", json=store_data)
        if response.status_code == 200:
            store = response.json()
            self.store_id = store["id"]
            print(f"   ✅ Store created with ID: {self.store_id}")
        else:
            print(f"   ⚠️  Store creation failed (may already exist): {response.status_code}")
            
            # Try to get existing store
            response = await self.client.get("/api/v1/stores/")
            if response.status_code == 200:
                stores = response.json()
                for store in stores:
                    if store["url"] == TEST_STORE_URL:
                        self.store_id = store["id"]
                        print(f"   ✅ Found existing store with ID: {self.store_id}")
                        break
        
        if self.store_id:
            # Get store
            print(f"   Getting store {self.store_id}...")
            response = await self.client.get(f"/api/v1/stores/{self.store_id}")
            assert response.status_code == 200
            print(f"   ✅ Store retrieved successfully")
            
            # Update store
            print(f"   Updating store {self.store_id}...")
            update_data = {"description": "Updated description"}
            response = await self.client.patch(f"/api/v1/stores/{self.store_id}", json=update_data)
            assert response.status_code == 200
            print(f"   ✅ Store updated successfully")
            
            # Trigger scan
            print(f"   Triggering scan for store {self.store_id}...")
            response = await self.client.post(f"/api/v1/stores/{self.store_id}/scan")
            if response.status_code == 200:
                print(f"   ✅ Scan triggered successfully")
            else:
                print(f"   ⚠️  Scan trigger failed: {response.status_code}")
        
        return self.store_id
        
    async def test_monitor_endpoints(self):
        """Test monitor endpoints"""
        if not self.store_id:
            print("\n⚠️  Skipping monitor tests (no store ID)")
            return
            
        print("\n🔍 Testing monitor endpoints...")
        
        # Get inventory
        print(f"   Getting inventory for store {self.store_id}...")
        response = await self.client.get(f"/api/v1/monitor/inventory/{self.store_id}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Inventory retrieved")
            print(f"      - Products: {len(data.get('products', []))}")
            print(f"      - Total stock: {data['statistics']['total_stock']}")
        else:
            print(f"   ⚠️  No inventory data yet (need successful scan first)")
        
        # Get alerts
        print("   Getting stock alerts...")
        response = await self.client.get("/api/v1/monitor/alerts")
        assert response.status_code == 200
        alerts = response.json()
        print(f"   ✅ Retrieved {len(alerts)} alerts")
        
        # Get low stock items
        print("   Getting low stock items...")
        response = await self.client.get("/api/v1/monitor/low-stock-items?threshold=20")
        assert response.status_code == 200
        data = response.json()
        print(f"   ✅ Found {data['total_items']} low stock items")
        
    async def test_analytics(self):
        """Test analytics endpoints"""
        print("\n🔍 Testing analytics endpoints...")
        
        # Overview
        print("   Getting analytics overview...")
        response = await self.client.get("/api/v1/analytics/overview?days=7")
        assert response.status_code == 200
        data = response.json()
        print(f"   ✅ Analytics overview retrieved")
        print(f"      - Total scans: {data['scans']['total']}")
        print(f"      - Success rate: {data['scans']['success_rate']}%")
        
        # Daily summary
        print("   Getting daily summary...")
        response = await self.client.get("/api/v1/analytics/reports/daily-summary")
        assert response.status_code == 200
        data = response.json()
        print(f"   ✅ Daily summary retrieved for {data['date']}")
        
    async def test_webhooks(self):
        """Test webhook endpoints"""
        print("\n🔍 Testing webhook endpoints...")
        
        if not self.store_id:
            print("   ⚠️  Skipping webhook tests (no store ID)")
            return
        
        # Create webhook
        print("   Creating webhook...")
        webhook_data = {
            "store_id": self.store_id,
            "url": "https://webhook.site/test",
            "events": ["low_stock", "out_of_stock"],
            "enabled": True,
            "secret": "test-secret"
        }
        
        response = await self.client.post("/api/v1/webhooks/", json=webhook_data)
        if response.status_code == 200:
            webhook = response.json()
            webhook_id = webhook["id"]
            print(f"   ✅ Webhook created with ID: {webhook_id}")
            
            # Test webhook
            print(f"   Testing webhook {webhook_id}...")
            response = await self.client.post(f"/api/v1/webhooks/{webhook_id}/test")
            assert response.status_code == 200
            print(f"   ✅ Test webhook sent")
            
            # Delete webhook
            print(f"   Deleting webhook {webhook_id}...")
            response = await self.client.delete(f"/api/v1/webhooks/{webhook_id}")
            assert response.status_code == 200
            print(f"   ✅ Webhook deleted")
        else:
            print(f"   ⚠️  Webhook creation failed: {response.status_code}")
    
    async def cleanup(self):
        """Cleanup test data"""
        if self.store_id:
            print(f"\n🧹 Cleaning up test store {self.store_id}...")
            response = await self.client.delete(f"/api/v1/stores/{self.store_id}")
            if response.status_code == 200:
                print(f"   ✅ Test store deleted")
            else:
                print(f"   ⚠️  Could not delete test store")
        
        await self.client.aclose()
    
    async def run_all_tests(self):
        """Run all tests"""
        print("=" * 60)
        print("🚀 Starting Shopify Monitor API Tests")
        print("=" * 60)
        
        try:
            # Basic tests
            await self.test_health()
            await self.test_dashboard()
            
            # Quick scan test
            await self.test_quick_scan()
            
            # CRUD tests
            await self.test_store_crud()
            
            # Feature tests
            await self.test_monitor_endpoints()
            await self.test_analytics()
            await self.test_webhooks()
            
            print("\n" + "=" * 60)
            print("✅ All tests completed successfully!")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.cleanup()


async def main():
    tester = APITester()
    await tester.run_all_tests()


if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════════╗
║         Shopify Monitor API Test Suite                   ║
║                                                          ║
║  Testing API: {BASE_URL:<42} ║
║  API Key: {API_KEY:<46} ║
║  Test Store: {TEST_STORE_URL:<42} ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    asyncio.run(main())