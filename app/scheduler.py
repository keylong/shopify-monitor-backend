"""
Background task scheduler for automated monitoring
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
from loguru import logger
from typing import Optional
import asyncio

from app.database import SessionLocal
from app.models.database import Store, ScanResult, InventoryHistory, StockAlert
from app.services.shopify_scraper import ShopifyScraperService


class MonitorScheduler:
    """Monitoring task scheduler"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.running_scans = set()  # Track running scans to prevent duplicates
        
    def start(self):
        """Start the scheduler"""
        # Add job to check for stores that need scanning
        self.scheduler.add_job(
            self.scan_stores,
            trigger=IntervalTrigger(seconds=60),  # Check every minute
            id="scan_stores",
            replace_existing=True,
            max_instances=1
        )
        
        # Add cleanup job
        self.scheduler.add_job(
            self.cleanup_old_data,
            trigger=IntervalTrigger(hours=24),  # Daily cleanup
            id="cleanup_old_data",
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("📅 Scheduler started")
        
    def shutdown(self):
        """Shutdown the scheduler"""
        self.scheduler.shutdown(wait=True)
        logger.info("📅 Scheduler stopped")
        
    async def scan_stores(self):
        """Scan stores that are due for monitoring"""
        db = SessionLocal()
        try:
            # Get stores that need scanning
            now = datetime.utcnow()
            stores = db.query(Store).filter(
                Store.enabled == True,
                (Store.next_scan == None) | (Store.next_scan <= now)
            ).all()
            
            for store in stores:
                # Skip if already scanning
                if store.id in self.running_scans:
                    continue
                    
                # Schedule scan
                asyncio.create_task(self.scan_store(store.id))
                
        except Exception as e:
            logger.error(f"Error in scan_stores: {e}")
        finally:
            db.close()
            
    async def scan_store(self, store_id: int):
        """Scan a single store"""
        # Prevent duplicate scans
        if store_id in self.running_scans:
            return
            
        self.running_scans.add(store_id)
        db = SessionLocal()
        
        try:
            store = db.query(Store).filter(Store.id == store_id).first()
            if not store:
                return
                
            logger.info(f"🔍 Scanning store: {store.name}")
            
            # Create scraper instance
            scraper = ShopifyScraperService(store.url)
            
            # Perform scan
            result = await scraper.scan_inventory()
            
            # Save scan result
            scan_result = ScanResult(
                store_id=store.id,
                success=result.get("success", False),
                error=result.get("error"),
                scan_duration=result.get("scan_duration"),
                total_products=result.get("statistics", {}).get("total_products", 0),
                valid_variants=result.get("statistics", {}).get("valid_variants", 0),
                added_to_cart=result.get("statistics", {}).get("added_to_cart", 0),
                failed_to_add=result.get("statistics", {}).get("failed_to_add", 0),
                inventory_found=result.get("statistics", {}).get("inventory_found", 0),
                total_stock=result.get("statistics", {}).get("total_stock", 0),
                products_data=result.get("products"),
                inventory_data=result.get("inventory")
            )
            db.add(scan_result)
            
            # Update store statistics
            if result.get("success"):
                store.last_scan = datetime.utcnow()
                store.next_scan = datetime.utcnow() + timedelta(seconds=store.scan_interval)
                store.total_products = scan_result.total_products
                store.total_variants = scan_result.valid_variants
                store.total_stock = scan_result.total_stock
                
                # Save inventory history
                await self.save_inventory_history(db, store, result)
                
                # Check for stock alerts
                await self.check_stock_alerts(db, store, result)
            
            db.commit()
            logger.info(f"✅ Scan completed for {store.name}")
            
            # Cleanup
            await scraper.close()
            
        except Exception as e:
            logger.error(f"Error scanning store {store_id}: {e}")
            db.rollback()
        finally:
            self.running_scans.discard(store_id)
            db.close()
            
    async def save_inventory_history(self, db, store, result):
        """Save inventory history records"""
        products = result.get("products", [])
        
        for product in products:
            for variant in product.get("variants", []):
                if not variant.get("is_valid"):
                    continue
                    
                history = InventoryHistory(
                    store_id=store.id,
                    product_id=str(product.get("id")),
                    product_title=product.get("title"),
                    variant_id=str(variant.get("id")),
                    variant_title=variant.get("title"),
                    stock=variant.get("stock", 0),
                    price=variant.get("price"),
                    sku=variant.get("sku")
                )
                db.add(history)
                
    async def check_stock_alerts(self, db, store, result):
        """Check for stock alerts"""
        if not store.notify_low_stock:
            return
            
        products = result.get("products", [])
        
        for product in products:
            for variant in product.get("variants", []):
                if not variant.get("is_valid"):
                    continue
                    
                stock = variant.get("stock", 0)
                
                # Check for low stock
                if 0 < stock <= store.low_stock_threshold:
                    # Check if alert already exists
                    existing = db.query(StockAlert).filter(
                        StockAlert.store_id == store.id,
                        StockAlert.variant_id == str(variant.get("id")),
                        StockAlert.resolved == False
                    ).first()
                    
                    if not existing:
                        alert = StockAlert(
                            store_id=store.id,
                            product_id=str(product.get("id")),
                            product_title=product.get("title"),
                            variant_id=str(variant.get("id")),
                            variant_title=variant.get("title"),
                            alert_type="low_stock",
                            current_stock=stock,
                            threshold=store.low_stock_threshold
                        )
                        db.add(alert)
                        logger.warning(f"⚠️ Low stock alert: {product.get('title')} - {variant.get('title')}: {stock}")
                        
                # Check for out of stock
                elif stock == 0:
                    existing = db.query(StockAlert).filter(
                        StockAlert.store_id == store.id,
                        StockAlert.variant_id == str(variant.get("id")),
                        StockAlert.resolved == False
                    ).first()
                    
                    if not existing:
                        alert = StockAlert(
                            store_id=store.id,
                            product_id=str(product.get("id")),
                            product_title=product.get("title"),
                            variant_id=str(variant.get("id")),
                            variant_title=variant.get("title"),
                            alert_type="out_of_stock",
                            current_stock=0,
                            threshold=0
                        )
                        db.add(alert)
                        logger.warning(f"🚫 Out of stock: {product.get('title')} - {variant.get('title')}")
                        
    async def cleanup_old_data(self):
        """Clean up old data"""
        db = SessionLocal()
        try:
            # Delete scan results older than 30 days
            cutoff = datetime.utcnow() - timedelta(days=30)
            deleted = db.query(ScanResult).filter(
                ScanResult.timestamp < cutoff
            ).delete()
            
            # Delete resolved alerts older than 7 days
            alert_cutoff = datetime.utcnow() - timedelta(days=7)
            deleted_alerts = db.query(StockAlert).filter(
                StockAlert.resolved == True,
                StockAlert.resolved_at < alert_cutoff
            ).delete()
            
            db.commit()
            logger.info(f"🧹 Cleanup: Deleted {deleted} old scan results and {deleted_alerts} resolved alerts")
            
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")
            db.rollback()
        finally:
            db.close()


# Global scheduler instance
scheduler = MonitorScheduler()