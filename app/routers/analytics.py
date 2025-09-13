"""
Analytics and reporting routes
"""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional
from datetime import datetime, timedelta
import csv
import io
import json

from app.database import get_db
from app.models.database import Store, ScanResult, InventoryHistory, StockAlert

router = APIRouter()


@router.get("/overview")
async def get_analytics_overview(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Get analytics overview for all stores
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Store statistics
    total_stores = db.query(func.count(Store.id)).scalar()
    active_stores = db.query(func.count(Store.id)).filter(
        Store.enabled == True
    ).scalar()
    
    # Scan statistics
    total_scans = db.query(func.count(ScanResult.id)).filter(
        ScanResult.timestamp >= cutoff
    ).scalar()
    
    successful_scans = db.query(func.count(ScanResult.id)).filter(
        ScanResult.timestamp >= cutoff,
        ScanResult.success == True
    ).scalar()
    
    avg_scan_duration = db.query(func.avg(ScanResult.scan_duration)).filter(
        ScanResult.timestamp >= cutoff,
        ScanResult.success == True
    ).scalar() or 0
    
    # Alert statistics
    total_alerts = db.query(func.count(StockAlert.id)).filter(
        StockAlert.created_at >= cutoff
    ).scalar()
    
    unresolved_alerts = db.query(func.count(StockAlert.id)).filter(
        StockAlert.created_at >= cutoff,
        StockAlert.resolved == False
    ).scalar()
    
    # Product statistics from latest scans
    latest_totals = db.query(
        func.sum(Store.total_products).label("products"),
        func.sum(Store.total_variants).label("variants"),
        func.sum(Store.total_stock).label("stock")
    ).first()
    
    return {
        "period_days": days,
        "stores": {
            "total": total_stores,
            "active": active_stores,
            "inactive": total_stores - active_stores
        },
        "scans": {
            "total": total_scans,
            "successful": successful_scans,
            "failed": total_scans - successful_scans,
            "success_rate": round(successful_scans / total_scans * 100, 2) if total_scans > 0 else 0,
            "avg_duration_seconds": round(avg_scan_duration, 2)
        },
        "inventory": {
            "total_products": latest_totals.products or 0,
            "total_variants": latest_totals.variants or 0,
            "total_stock": latest_totals.stock or 0
        },
        "alerts": {
            "total": total_alerts,
            "resolved": total_alerts - unresolved_alerts,
            "unresolved": unresolved_alerts
        }
    }


@router.get("/store/{store_id}/analytics")
async def get_store_analytics(
    store_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Get detailed analytics for a specific store
    """
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Store not found")
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Scan performance
    scan_stats = db.query(
        func.count(ScanResult.id).label("total"),
        func.sum(func.cast(ScanResult.success, db.Integer)).label("successful"),
        func.avg(ScanResult.scan_duration).label("avg_duration"),
        func.min(ScanResult.scan_duration).label("min_duration"),
        func.max(ScanResult.scan_duration).label("max_duration")
    ).filter(
        ScanResult.store_id == store_id,
        ScanResult.timestamp >= cutoff
    ).first()
    
    # Stock trends
    stock_trend = db.query(
        func.date(InventoryHistory.timestamp).label("date"),
        func.sum(InventoryHistory.stock).label("total_stock")
    ).filter(
        InventoryHistory.store_id == store_id,
        InventoryHistory.timestamp >= cutoff
    ).group_by(
        func.date(InventoryHistory.timestamp)
    ).order_by("date").all()
    
    # Top selling (most stock changes)
    top_movers = db.query(
        InventoryHistory.product_title,
        InventoryHistory.variant_title,
        func.max(InventoryHistory.stock).label("max_stock"),
        func.min(InventoryHistory.stock).label("min_stock"),
        func.count(InventoryHistory.id).label("scan_count")
    ).filter(
        InventoryHistory.store_id == store_id,
        InventoryHistory.timestamp >= cutoff
    ).group_by(
        InventoryHistory.product_title,
        InventoryHistory.variant_title
    ).having(
        func.max(InventoryHistory.stock) - func.min(InventoryHistory.stock) > 0
    ).order_by(
        (func.max(InventoryHistory.stock) - func.min(InventoryHistory.stock)).desc()
    ).limit(10).all()
    
    return {
        "store": {
            "id": store.id,
            "name": store.name,
            "url": store.url
        },
        "period_days": days,
        "scan_performance": {
            "total_scans": scan_stats.total or 0,
            "successful_scans": scan_stats.successful or 0,
            "success_rate": round((scan_stats.successful or 0) / (scan_stats.total or 1) * 100, 2),
            "avg_duration": round(scan_stats.avg_duration or 0, 2),
            "min_duration": round(scan_stats.min_duration or 0, 2),
            "max_duration": round(scan_stats.max_duration or 0, 2)
        },
        "stock_trend": [
            {
                "date": str(t.date),
                "total_stock": t.total_stock
            }
            for t in stock_trend
        ],
        "top_movers": [
            {
                "product": m.product_title,
                "variant": m.variant_title,
                "stock_change": m.max_stock - m.min_stock,
                "scan_count": m.scan_count
            }
            for m in top_movers
        ]
    }


@router.get("/export/inventory")
async def export_inventory(
    store_id: Optional[int] = None,
    format: str = Query("csv", regex="^(csv|json)$"),
    db: Session = Depends(get_db)
):
    """
    Export current inventory data
    """
    # Build query
    if store_id:
        stores = db.query(Store).filter(Store.id == store_id).all()
    else:
        stores = db.query(Store).all()
    
    if format == "json":
        # JSON export
        data = []
        for store in stores:
            # Get latest scan
            latest_scan = db.query(ScanResult).filter(
                ScanResult.store_id == store.id,
                ScanResult.success == True
            ).order_by(ScanResult.timestamp.desc()).first()
            
            if latest_scan and latest_scan.products_data:
                for product in latest_scan.products_data:
                    for variant in product.get("variants", []):
                        data.append({
                            "store_name": store.name,
                            "store_url": store.url,
                            "product_id": product.get("id"),
                            "product_title": product.get("title"),
                            "variant_id": variant.get("id"),
                            "variant_title": variant.get("title"),
                            "sku": variant.get("sku"),
                            "price": variant.get("price"),
                            "stock": variant.get("stock", 0),
                            "available": variant.get("available"),
                            "last_updated": latest_scan.timestamp.isoformat()
                        })
        
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            }
        )
    
    else:
        # CSV export
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "Store Name", "Store URL", "Product ID", "Product Title",
            "Variant ID", "Variant Title", "SKU", "Price", "Stock",
            "Available", "Last Updated"
        ])
        
        # Write data
        for store in stores:
            latest_scan = db.query(ScanResult).filter(
                ScanResult.store_id == store.id,
                ScanResult.success == True
            ).order_by(ScanResult.timestamp.desc()).first()
            
            if latest_scan and latest_scan.products_data:
                for product in latest_scan.products_data:
                    for variant in product.get("variants", []):
                        writer.writerow([
                            store.name,
                            store.url,
                            product.get("id"),
                            product.get("title"),
                            variant.get("id"),
                            variant.get("title"),
                            variant.get("sku", ""),
                            variant.get("price", ""),
                            variant.get("stock", 0),
                            "Yes" if variant.get("available") else "No",
                            latest_scan.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                        ])
        
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )


@router.get("/reports/daily-summary")
async def get_daily_summary(
    date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get daily summary report
    """
    if date:
        target_date = datetime.strptime(date, "%Y-%m-%d")
    else:
        target_date = datetime.utcnow().date()
    
    # Date range for the day
    start = datetime.combine(target_date, datetime.min.time())
    end = start + timedelta(days=1)
    
    # Scan summary
    scans = db.query(
        ScanResult.store_id,
        Store.name,
        func.count(ScanResult.id).label("scan_count"),
        func.sum(func.cast(ScanResult.success, db.Integer)).label("successful"),
        func.avg(ScanResult.scan_duration).label("avg_duration")
    ).join(
        Store, Store.id == ScanResult.store_id
    ).filter(
        ScanResult.timestamp >= start,
        ScanResult.timestamp < end
    ).group_by(
        ScanResult.store_id,
        Store.name
    ).all()
    
    # Alert summary
    alerts = db.query(
        StockAlert.alert_type,
        func.count(StockAlert.id).label("count")
    ).filter(
        StockAlert.created_at >= start,
        StockAlert.created_at < end
    ).group_by(
        StockAlert.alert_type
    ).all()
    
    return {
        "date": str(target_date),
        "scan_summary": [
            {
                "store_id": s.store_id,
                "store_name": s.name,
                "total_scans": s.scan_count,
                "successful_scans": s.successful or 0,
                "avg_duration": round(s.avg_duration or 0, 2)
            }
            for s in scans
        ],
        "alert_summary": {
            a.alert_type: a.count for a in alerts
        },
        "totals": {
            "total_scans": sum(s.scan_count for s in scans),
            "total_alerts": sum(a.count for a in alerts)
        }
    }