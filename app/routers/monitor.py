"""
Monitoring and inventory routes
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional, Dict
from datetime import datetime, timedelta

from app.database import get_db
from app.models import schemas
from app.models.database import Store, ScanResult, InventoryHistory, StockAlert

router = APIRouter()


@router.get("/inventory/{store_id}")
async def get_current_inventory(
    store_id: int,
    db: Session = Depends(get_db)
):
    """
    Get current inventory for a store from the latest scan
    """
    # Get latest scan result
    latest_scan = db.query(ScanResult).filter(
        ScanResult.store_id == store_id,
        ScanResult.success == True
    ).order_by(ScanResult.timestamp.desc()).first()
    
    if not latest_scan:
        raise HTTPException(status_code=404, detail="No successful scan found for this store")
    
    return {
        "store_id": store_id,
        "scan_timestamp": latest_scan.timestamp,
        "products": latest_scan.products_data,
        "inventory": latest_scan.inventory_data,
        "statistics": {
            "total_products": latest_scan.total_products,
            "total_variants": latest_scan.valid_variants,
            "total_stock": latest_scan.total_stock
        }
    }


@router.get("/inventory-history/{store_id}")
async def get_inventory_history(
    store_id: int,
    product_id: Optional[str] = None,
    variant_id: Optional[str] = None,
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db)
):
    """
    Get inventory history for a store
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    query = db.query(InventoryHistory).filter(
        InventoryHistory.store_id == store_id,
        InventoryHistory.timestamp >= cutoff
    )
    
    if product_id:
        query = query.filter(InventoryHistory.product_id == product_id)
    
    if variant_id:
        query = query.filter(InventoryHistory.variant_id == variant_id)
    
    history = query.order_by(InventoryHistory.timestamp.desc()).limit(1000).all()
    
    return {
        "store_id": store_id,
        "period_days": days,
        "total_records": len(history),
        "history": [
            {
                "timestamp": h.timestamp,
                "product_id": h.product_id,
                "product_title": h.product_title,
                "variant_id": h.variant_id,
                "variant_title": h.variant_title,
                "stock": h.stock,
                "price": h.price
            }
            for h in history
        ]
    }


@router.get("/stock-changes/{store_id}")
async def get_stock_changes(
    store_id: int,
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db)
):
    """
    Get stock level changes over time
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    
    # Get inventory snapshots
    history = db.query(
        InventoryHistory.variant_id,
        InventoryHistory.product_title,
        InventoryHistory.variant_title,
        func.min(InventoryHistory.stock).label("min_stock"),
        func.max(InventoryHistory.stock).label("max_stock"),
        func.avg(InventoryHistory.stock).label("avg_stock")
    ).filter(
        InventoryHistory.store_id == store_id,
        InventoryHistory.timestamp >= cutoff
    ).group_by(
        InventoryHistory.variant_id,
        InventoryHistory.product_title,
        InventoryHistory.variant_title
    ).all()
    
    changes = []
    for h in history:
        stock_change = h.max_stock - h.min_stock
        if stock_change != 0:  # Only show items with changes
            changes.append({
                "variant_id": h.variant_id,
                "product_title": h.product_title,
                "variant_title": h.variant_title,
                "min_stock": h.min_stock,
                "max_stock": h.max_stock,
                "avg_stock": round(h.avg_stock, 2),
                "stock_change": stock_change
            })
    
    # Sort by absolute stock change
    changes.sort(key=lambda x: abs(x["stock_change"]), reverse=True)
    
    return {
        "store_id": store_id,
        "period_hours": hours,
        "total_changes": len(changes),
        "changes": changes
    }


@router.get("/alerts", response_model=List[schemas.StockAlert])
async def get_stock_alerts(
    store_id: Optional[int] = None,
    alert_type: Optional[str] = None,
    resolved: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Get stock alerts
    """
    query = db.query(StockAlert)
    
    if store_id:
        query = query.filter(StockAlert.store_id == store_id)
    
    if alert_type:
        query = query.filter(StockAlert.alert_type == alert_type)
    
    if resolved is not None:
        query = query.filter(StockAlert.resolved == resolved)
    
    alerts = query.order_by(
        StockAlert.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    return alerts


@router.patch("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db)
):
    """
    Mark an alert as resolved
    """
    alert = db.query(StockAlert).filter(StockAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.resolved = True
    alert.resolved_at = datetime.utcnow()
    
    db.commit()
    
    return {"success": True, "message": "Alert resolved"}


@router.post("/scan/{store_id}")
async def scan_store(
    store_id: int,
    db: Session = Depends(get_db)
):
    """
    Trigger a scan for a specific store
    """
    from app.scheduler import scheduler
    import asyncio
    
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Trigger scan asynchronously
    asyncio.create_task(scheduler.scan_store(store_id))
    
    return {
        "success": True,
        "message": f"Scan triggered for store: {store.name}",
        "store_id": store_id
    }


@router.get("/history/{store_id}", response_model=List[schemas.ScanResult])
async def get_scan_history(
    store_id: int,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get scan history for a store
    """
    scans = db.query(ScanResult).filter(
        ScanResult.store_id == store_id
    ).order_by(
        ScanResult.timestamp.desc()
    ).limit(limit).all()
    
    return scans


@router.get("/latest/{store_id}", response_model=schemas.ScanResult)
async def get_latest_scan(
    store_id: int,
    db: Session = Depends(get_db)
):
    """
    Get the latest scan result for a store
    """
    scan = db.query(ScanResult).filter(
        ScanResult.store_id == store_id
    ).order_by(
        ScanResult.timestamp.desc()
    ).first()
    
    if not scan:
        raise HTTPException(status_code=404, detail="No scan results found for this store")
    
    return scan


@router.get("/low-stock-items")
async def get_low_stock_items(
    threshold: int = Query(10, ge=0),
    db: Session = Depends(get_db)
):
    """
    Get all items across all stores that are low in stock
    """
    # Get latest inventory for each store
    subquery = db.query(
        ScanResult.store_id,
        func.max(ScanResult.timestamp).label("max_timestamp")
    ).filter(
        ScanResult.success == True
    ).group_by(ScanResult.store_id).subquery()
    
    # Get latest successful scans
    latest_scans = db.query(ScanResult).join(
        subquery,
        and_(
            ScanResult.store_id == subquery.c.store_id,
            ScanResult.timestamp == subquery.c.max_timestamp
        )
    ).all()
    
    low_stock_items = []
    
    for scan in latest_scans:
        store = db.query(Store).filter(Store.id == scan.store_id).first()
        if not store or not scan.products_data:
            continue
        
        for product in scan.products_data:
            for variant in product.get("variants", []):
                stock = variant.get("stock", 0)
                if 0 < stock <= threshold:
                    low_stock_items.append({
                        "store_name": store.name,
                        "store_id": store.id,
                        "product_title": product.get("title"),
                        "variant_title": variant.get("title"),
                        "sku": variant.get("sku"),
                        "stock": stock,
                        "price": variant.get("price")
                    })
    
    # Sort by stock level
    low_stock_items.sort(key=lambda x: x["stock"])
    
    return {
        "threshold": threshold,
        "total_items": len(low_stock_items),
        "items": low_stock_items
    }