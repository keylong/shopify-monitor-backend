"""
Webhook management routes
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import httpx
import hashlib
import hmac
import json
from datetime import datetime

from app.database import get_db
from app.models import schemas
from app.models.database import Store, WebhookConfig
from loguru import logger

router = APIRouter()


@router.get("/", response_model=List[schemas.WebhookConfig])
async def list_webhooks(
    store_id: int = None,
    db: Session = Depends(get_db)
):
    """
    List all webhook configurations
    """
    query = db.query(WebhookConfig)
    
    if store_id:
        query = query.filter(WebhookConfig.store_id == store_id)
    
    webhooks = query.all()
    return webhooks


@router.post("/", response_model=schemas.WebhookConfig)
async def create_webhook(
    webhook: schemas.WebhookConfig,
    db: Session = Depends(get_db)
):
    """
    Create a new webhook configuration
    """
    # Verify store exists
    store = db.query(Store).filter(Store.id == webhook.store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    db_webhook = WebhookConfig(
        store_id=webhook.store_id,
        url=str(webhook.url),
        events=webhook.events,
        enabled=webhook.enabled,
        secret=webhook.secret
    )
    
    db.add(db_webhook)
    db.commit()
    db.refresh(db_webhook)
    
    return db_webhook


@router.patch("/{webhook_id}", response_model=schemas.WebhookConfig)
async def update_webhook(
    webhook_id: int,
    webhook_update: dict,
    db: Session = Depends(get_db)
):
    """
    Update a webhook configuration
    """
    webhook = db.query(WebhookConfig).filter(WebhookConfig.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    for field, value in webhook_update.items():
        if hasattr(webhook, field):
            setattr(webhook, field, value)
    
    webhook.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(webhook)
    
    return webhook


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a webhook configuration
    """
    webhook = db.query(WebhookConfig).filter(WebhookConfig.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    db.delete(webhook)
    db.commit()
    
    return {"success": True, "message": "Webhook deleted successfully"}


@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Test a webhook by sending a test payload
    """
    webhook = db.query(WebhookConfig).filter(WebhookConfig.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    # Test payload
    test_payload = {
        "event": "test",
        "timestamp": datetime.utcnow().isoformat(),
        "webhook_id": webhook_id,
        "store_id": webhook.store_id,
        "message": "This is a test webhook notification"
    }
    
    # Send webhook in background
    background_tasks.add_task(
        send_webhook,
        webhook,
        test_payload
    )
    
    return {
        "success": True,
        "message": "Test webhook sent",
        "webhook_url": webhook.url
    }


async def send_webhook(webhook: WebhookConfig, payload: dict):
    """
    Send webhook notification
    """
    try:
        # Generate signature if secret is configured
        headers = {"Content-Type": "application/json"}
        
        if webhook.secret:
            # Create HMAC signature
            signature = hmac.new(
                webhook.secret.encode(),
                json.dumps(payload).encode(),
                hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature"] = signature
        
        # Send webhook
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook.url,
                json=payload,
                headers=headers,
                timeout=10.0
            )
            
            # Update webhook stats
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                webhook_db = db.query(WebhookConfig).filter(
                    WebhookConfig.id == webhook.id
                ).first()
                
                if webhook_db:
                    webhook_db.last_triggered = datetime.utcnow()
                    webhook_db.trigger_count += 1
                    
                    if response.status_code >= 400:
                        webhook_db.last_error = f"HTTP {response.status_code}: {response.text[:500]}"
                    else:
                        webhook_db.last_error = None
                    
                    db.commit()
            finally:
                db.close()
            
            if response.status_code >= 400:
                logger.error(f"Webhook failed: {webhook.url} - {response.status_code}")
            else:
                logger.info(f"Webhook sent successfully: {webhook.url}")
                
    except Exception as e:
        logger.error(f"Webhook error for {webhook.url}: {str(e)}")
        
        # Update error in database
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            webhook_db = db.query(WebhookConfig).filter(
                WebhookConfig.id == webhook.id
            ).first()
            
            if webhook_db:
                webhook_db.last_error = str(e)[:500]
                db.commit()
        finally:
            db.close()


def trigger_webhook_event(store_id: int, event_type: str, data: dict):
    """
    Trigger webhooks for a specific event
    """
    from app.database import SessionLocal
    db = SessionLocal()
    
    try:
        # Get enabled webhooks for this store and event
        webhooks = db.query(WebhookConfig).filter(
            WebhookConfig.store_id == store_id,
            WebhookConfig.enabled == True
        ).all()
        
        for webhook in webhooks:
            if event_type in webhook.events:
                payload = {
                    "event": event_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    "store_id": store_id,
                    "data": data
                }
                
                # Send webhook asynchronously
                import asyncio
                asyncio.create_task(send_webhook(webhook, payload))
                
    finally:
        db.close()