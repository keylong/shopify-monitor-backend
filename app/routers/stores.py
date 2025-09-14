"""
Store management routes
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models import schemas
from app.models.database import Store, ScanResult

router = APIRouter()


@router.get("/", response_model=List[schemas.Store])
async def list_stores(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    enabled_only: bool = False,
    db: Session = Depends(get_db)
):
    """
    List all stores with pagination
    """
    query = db.query(Store)
    
    if enabled_only:
        query = query.filter(Store.enabled == True)
    
    stores = query.offset(skip).limit(limit).all()
    return stores


@router.get("/{store_id}", response_model=schemas.Store)
async def get_store(store_id: int, db: Session = Depends(get_db)):
    """
    Get a specific store by ID
    """
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.post("/", response_model=schemas.Store)
async def create_store(
    store: schemas.StoreCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new store
    """
    # Check if URL already exists
    existing = db.query(Store).filter(Store.url == str(store.url)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Store with this URL already exists")
    
    db_store = Store(
        name=store.name,
        url=str(store.url),
        description=store.description,
        scan_interval=store.scan_interval,
        enabled=store.enabled,
        notify_low_stock=store.notify_low_stock,
        low_stock_threshold=store.low_stock_threshold
    )
    
    db.add(db_store)
    db.commit()
    db.refresh(db_store)
    
    return db_store


@router.put("/{store_id}", response_model=schemas.Store)
async def update_store(
    store_id: int,
    store_update: schemas.StoreUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a store
    """
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Update fields if provided
    update_data = store_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(store, field, value)
    
    store.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(store)
    
    return store

@router.patch("/{store_id}", response_model=schemas.Store)
async def patch_store(
    store_id: int,
    store_update: schemas.StoreUpdate,
    db: Session = Depends(get_db)
):
    """
    Partially update a store (PATCH method)
    """
    return await update_store(store_id, store_update, db)


@router.delete("/{store_id}")
async def delete_store(store_id: int, db: Session = Depends(get_db)):
    """
    Delete a store
    """
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    db.delete(store)
    db.commit()
    
    return {"success": True, "message": "Store deleted successfully"}


@router.get("/{store_id}/scan-history", response_model=List[schemas.ScanResult])
async def get_scan_history(
    store_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Get scan history for a store
    """
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    scans = db.query(ScanResult).filter(
        ScanResult.store_id == store_id
    ).order_by(
        ScanResult.timestamp.desc()
    ).offset(skip).limit(limit).all()
    
    return scans


@router.post("/{store_id}/toggle", response_model=schemas.Store)
async def toggle_store(
    store_id: int,
    db: Session = Depends(get_db)
):
    """
    Toggle store enabled/disabled status
    """
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Toggle the enabled status
    store.enabled = not store.enabled
    store.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(store)
    
    return store


@router.post("/{store_id}/scan")
async def trigger_scan(
    store_id: int,
    db: Session = Depends(get_db)
):
    """
    Trigger an immediate scan for a store
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