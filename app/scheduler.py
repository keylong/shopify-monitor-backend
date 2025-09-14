"""
Background task scheduler for automated monitoring
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
from loguru import logger
from typing import Optional
import asyncio

from app.database import SessionLocal, get_db_session
from app.models.database import Store, ScanResult
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
        
        try:
            # Step 1: Get store info (short DB connection)
            store = await self._get_store_info(store_id)
            if not store:
                return
                
            logger.info(f"🔍 Scanning store: {store.name}")
            
            # Step 2: Perform scan (no DB connection held)
            scraper = ShopifyScraperService(store.url)
            result = await scraper.scan_inventory()
            await scraper.close()
            
            # Step 3: Save results (new DB connection)
            await self._save_scan_results(store_id, store, result)
            
        except Exception as e:
            logger.error(f"Error scanning store {store_id}: {e}")
        finally:
            self.running_scans.discard(store_id)
    
    async def _get_store_info(self, store_id: int):
        """Get store information with short-lived connection"""
        db = get_db_session()
        try:
            store = db.query(Store).filter(Store.id == store_id).first()
            if store:
                # Convert to dict to avoid detached instance issues
                return {
                    'id': store.id,
                    'name': store.name,
                    'url': store.url,
                    'scan_interval': store.scan_interval,
                    'notify_low_stock': store.notify_low_stock,
                    'low_stock_threshold': store.low_stock_threshold
                }
            return None
        except Exception as e:
            logger.error(f"Error getting store info: {e}")
            return None
        finally:
            try:
                db.close()
            except Exception as e:
                logger.warning(f"Error closing store info session: {e}")
    
    async def _save_scan_results(self, store_id: int, store_info: dict, result: dict):
        """Save scan results with fresh DB connection - PURE DATA STORAGE"""
        db = get_db_session()
        try:
            # Get fresh store instance
            store = db.query(Store).filter(Store.id == store_id).first()
            if not store:
                return
                
            # Save scan result only - NO business logic
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
            
            # Update basic store statistics only
            if result.get("success"):
                store.last_scan = datetime.utcnow()
                store.next_scan = datetime.utcnow() + timedelta(seconds=store_info.get('scan_interval', 3600))
                store.total_products = scan_result.total_products
                store.total_variants = scan_result.valid_variants
                store.total_stock = scan_result.total_stock
            
            db.commit()
            logger.info(f"✅ 扫描数据已保存: {store_info['name']}")
            
        except Exception as e:
            logger.error(f"保存扫描结果错误 store {store_id}: {e}")
            try:
                db.rollback()
            except Exception as rollback_error:
                logger.error(f"回滚错误: {rollback_error}")
            raise
        finally:
            try:
                db.close()
            except Exception as e:
                logger.warning(f"关闭数据库会话错误: {e}")
            
                        
    async def cleanup_old_data(self):
        """Clean up old scan results only"""
        db = SessionLocal()
        try:
            # Delete scan results older than 30 days
            cutoff = datetime.utcnow() - timedelta(days=30)
            deleted = db.query(ScanResult).filter(
                ScanResult.timestamp < cutoff
            ).delete()
            
            db.commit()
            logger.info(f"🧹 清理完成: 删除了 {deleted} 条旧的扫描记录")
            
        except Exception as e:
            logger.error(f"清理数据错误: {e}")
            db.rollback()
        finally:
            db.close()


# Global scheduler instance
scheduler = MonitorScheduler()