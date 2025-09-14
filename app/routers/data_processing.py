"""
数据处理API - 支持前端业务逻辑
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.database import get_db
from app.models.database import InventoryHistory, StockAlert
from app.models import schemas

router = APIRouter()


class InventoryHistoryCreate(BaseModel):
    """库存历史记录创建模型"""
    store_id: int
    product_id: str
    product_title: str
    variant_id: str
    variant_title: str
    stock: int
    price: float = None
    sku: str = None
    timestamp: str


class StockAlertCreate(BaseModel):
    """库存警报创建模型"""
    store_id: int
    product_id: str
    product_title: str
    variant_id: str
    variant_title: str
    alert_type: str
    current_stock: int
    threshold: int = None


@router.post("/inventory-history/batch")
async def create_inventory_history_batch(
    history_records: List[InventoryHistoryCreate],
    db: Session = Depends(get_db)
):
    """
    批量创建库存历史记录
    """
    try:
        db_records = []
        for record in history_records:
            db_record = InventoryHistory(
                store_id=record.store_id,
                product_id=record.product_id,
                product_title=record.product_title,
                variant_id=record.variant_id,
                variant_title=record.variant_title,
                stock=record.stock,
                price=record.price,
                sku=record.sku,
                timestamp=datetime.fromisoformat(record.timestamp.replace('Z', '+00:00'))
            )
            db_records.append(db_record)
        
        db.add_all(db_records)
        db.commit()
        
        return {
            "success": True,
            "message": f"Successfully created {len(db_records)} inventory history records",
            "created_count": len(db_records)
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create inventory history: {str(e)}")


@router.post("/alerts")
async def create_stock_alert(
    alert: StockAlertCreate,
    db: Session = Depends(get_db)
):
    """
    创建库存警报
    """
    try:
        # 检查是否已存在相同的未解决警报
        existing_alert = db.query(StockAlert).filter(
            StockAlert.store_id == alert.store_id,
            StockAlert.variant_id == alert.variant_id,
            StockAlert.resolved == False
        ).first()
        
        if existing_alert:
            return {
                "success": False,
                "message": "Alert already exists for this variant",
                "alert_id": existing_alert.id
            }
        
        db_alert = StockAlert(
            store_id=alert.store_id,
            product_id=alert.product_id,
            product_title=alert.product_title,
            variant_id=alert.variant_id,
            variant_title=alert.variant_title,
            alert_type=alert.alert_type,
            current_stock=alert.current_stock,
            threshold=alert.threshold,
            created_at=datetime.utcnow(),
            resolved=False
        )
        
        db.add(db_alert)
        db.commit()
        db.refresh(db_alert)
        
        return {
            "success": True,
            "message": "Stock alert created successfully",
            "alert_id": db_alert.id,
            "alert": {
                "id": db_alert.id,
                "store_id": db_alert.store_id,
                "product_title": db_alert.product_title,
                "variant_title": db_alert.variant_title,
                "alert_type": db_alert.alert_type,
                "current_stock": db_alert.current_stock,
                "threshold": db_alert.threshold,
                "created_at": db_alert.created_at.isoformat(),
                "resolved": db_alert.resolved
            }
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create stock alert: {str(e)}")


@router.post("/alerts/batch")
async def create_stock_alerts_batch(
    alerts: List[StockAlertCreate],
    db: Session = Depends(get_db)
):
    """
    批量创建库存警报
    """
    try:
        created_alerts = []
        skipped_alerts = []
        
        for alert_data in alerts:
            # 检查是否已存在
            existing_alert = db.query(StockAlert).filter(
                StockAlert.store_id == alert_data.store_id,
                StockAlert.variant_id == alert_data.variant_id,
                StockAlert.resolved == False
            ).first()
            
            if existing_alert:
                skipped_alerts.append({
                    "variant_id": alert_data.variant_id,
                    "reason": "Already exists"
                })
                continue
            
            db_alert = StockAlert(
                store_id=alert_data.store_id,
                product_id=alert_data.product_id,
                product_title=alert_data.product_title,
                variant_id=alert_data.variant_id,
                variant_title=alert_data.variant_title,
                alert_type=alert_data.alert_type,
                current_stock=alert_data.current_stock,
                threshold=alert_data.threshold,
                created_at=datetime.utcnow(),
                resolved=False
            )
            
            db.add(db_alert)
            created_alerts.append(alert_data.variant_id)
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Created {len(created_alerts)} alerts, skipped {len(skipped_alerts)}",
            "created_count": len(created_alerts),
            "skipped_count": len(skipped_alerts),
            "created_alerts": created_alerts,
            "skipped_alerts": skipped_alerts
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create stock alerts: {str(e)}")


@router.delete("/alerts/resolved/cleanup")
async def cleanup_resolved_alerts(
    days_old: int = 7,
    db: Session = Depends(get_db)
):
    """
    清理已解决的旧警报
    """
    try:
        cutoff = datetime.utcnow() - timedelta(days=days_old)
        deleted_count = db.query(StockAlert).filter(
            StockAlert.resolved == True,
            StockAlert.resolved_at < cutoff
        ).delete()
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Cleaned up {deleted_count} resolved alerts older than {days_old} days",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to cleanup alerts: {str(e)}")


@router.post("/process-scan-result")
async def process_scan_result(
    store_id: int,
    scan_result_id: int,
    db: Session = Depends(get_db)
):
    """
    处理扫描结果 - 由前端调用来触发数据处理
    """
    try:
        # 这个端点可以由前端在扫描完成后调用
        # 用于触发任何需要的数据处理逻辑
        
        return {
            "success": True,
            "message": f"Scan result {scan_result_id} for store {store_id} processed",
            "processed_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process scan result: {str(e)}")