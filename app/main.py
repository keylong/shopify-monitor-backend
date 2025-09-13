"""
FastAPI Main Application
Enterprise Shopify Monitor Backend
"""

from fastapi import FastAPI, Depends, HTTPException, Security, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse, FileResponse
from contextlib import asynccontextmanager
import uvicorn
from loguru import logger
from typing import List, Optional
import asyncio

from app.config import settings
from app.models import schemas
from app.models.database import Base
from app.services.shopify_scraper import ShopifyScraperService
from app.database import engine, SessionLocal, get_db
from app.scheduler import scheduler
from app.routers import stores, monitor, analytics, webhooks

# Configure logging
# Only add file logging if not in read-only environment (like Leapcell)
import os
import sys

# Check if we can write to filesystem
if os.environ.get("ENVIRONMENT") != "production":
    try:
        logger.add(
            settings.log_file,
            rotation="10 MB",
            retention="7 days",
            level=settings.log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} - {message}"
        )
    except (OSError, PermissionError):
        # Fallback to stdout only
        logger.add(
            sys.stdout,
            level=settings.log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} - {message}"
        )
else:
    # In production, only log to stdout
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} - {message}"
    )

# API Key Security
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify API key for authentication"""
    if not api_key or api_key not in settings.api_keys:
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing API key"
        )
    return api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("🚀 Starting Shopify Monitor API...")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database initialized")
    
    # Start scheduler if enabled and not using in-memory database
    if settings.enable_scheduler:
        # Don't start scheduler with in-memory database as data won't persist
        from app.database import DATABASE_URL
        if ":memory:" in DATABASE_URL:
            logger.warning("⚠️ Scheduler disabled - using in-memory database")
        else:
            scheduler.start()
            logger.info("✅ Scheduler started")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down...")
    if settings.enable_scheduler:
        scheduler.shutdown()
    logger.info("✅ Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Enterprise-grade Shopify inventory monitoring system",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint (no auth required)
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment
    }


# Root endpoint
@app.get("/", tags=["System"])
async def root():
    """Root endpoint with API information"""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "description": "Shopify Monitor API",
        "documentation": "/docs" if settings.debug else "Disabled in production",
        "endpoints": {
            "health": "/health",
            "stores": "/api/v1/stores",
            "monitor": "/api/v1/monitor",
            "analytics": "/api/v1/analytics",
            "webhooks": "/api/v1/webhooks"
        }
    }


# Quick scan endpoint
@app.post(
    "/api/v1/scan",
    response_model=schemas.ScanResult,
    tags=["Monitor"],
    dependencies=[Depends(verify_api_key)]
)
async def quick_scan(
    request: schemas.ScanRequest,
    background_tasks: BackgroundTasks
):
    """
    Perform a quick inventory scan for any Shopify store
    """
    try:
        scraper = ShopifyScraperService(
            store_url=str(request.store_url),
            use_proxy=request.use_proxy
        )
        
        result = await scraper.scan_inventory()
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        
        # Convert to schema
        scan_result = schemas.ScanResult(
            store_url=str(request.store_url),
            success=result["success"],
            timestamp=result["timestamp"],
            scan_duration=result.get("scan_duration"),
            statistics=schemas.ScanStatistics(**result.get("statistics", {})),
            products=[schemas.ProductInfo(**p) for p in result.get("products", [])],
            inventory=result.get("inventory", {})
        )
        
        await scraper.close()
        return scan_result
        
    except Exception as e:
        logger.error(f"Scan failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Dashboard statistics
@app.get(
    "/api/v1/dashboard",
    response_model=schemas.DashboardStats,
    tags=["Analytics"],
    dependencies=[Depends(verify_api_key)]
)
async def dashboard_stats(db: SessionLocal = Depends(get_db)):
    """
    Get dashboard statistics
    """
    from sqlalchemy import func
    from app.models.database import Store, ScanResult, InventoryHistory
    
    # Get statistics
    total_stores = db.query(func.count(Store.id)).scalar()
    active_stores = db.query(func.count(Store.id)).filter(Store.enabled == True).scalar()
    total_products = db.query(func.sum(Store.total_products)).scalar() or 0
    total_variants = db.query(func.sum(Store.total_variants)).scalar() or 0
    total_stock = db.query(func.sum(Store.total_stock)).scalar() or 0
    
    # Recent scans (last 24 hours)
    from datetime import datetime, timedelta
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_scans = db.query(func.count(ScanResult.id)).filter(
        ScanResult.timestamp >= yesterday
    ).scalar()
    
    failed_scans = db.query(func.count(ScanResult.id)).filter(
        ScanResult.timestamp >= yesterday,
        ScanResult.success == False
    ).scalar()
    
    # Average scan time
    avg_scan_time = db.query(func.avg(ScanResult.scan_duration)).filter(
        ScanResult.timestamp >= yesterday,
        ScanResult.success == True
    ).scalar() or 0
    
    return schemas.DashboardStats(
        total_stores=total_stores,
        active_stores=active_stores,
        total_products=total_products,
        total_variants=total_variants,
        total_stock=total_stock,
        recent_scans=recent_scans,
        failed_scans=failed_scans,
        average_scan_time=round(avg_scan_time, 2)
    )


# Include routers
app.include_router(
    stores.router,
    prefix="/api/v1/stores",
    tags=["Stores"],
    dependencies=[Depends(verify_api_key)]
)

app.include_router(
    monitor.router,
    prefix="/api/v1/monitor",
    tags=["Monitor"],
    dependencies=[Depends(verify_api_key)]
)

app.include_router(
    analytics.router,
    prefix="/api/v1/analytics",
    tags=["Analytics"],
    dependencies=[Depends(verify_api_key)]
)

app.include_router(
    webhooks.router,
    prefix="/api/v1/webhooks",
    tags=["Webhooks"],
    dependencies=[Depends(verify_api_key)]
)


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else None
        }
    )


if __name__ == "__main__":
    import os
    # Get host and port from environment or settings
    host = os.getenv("HOST", settings.host)
    port = int(os.getenv("PORT", settings.port))
    
    uvicorn.run(
        "app.main:app",
        host=host,  # Must be 0.0.0.0 for container
        port=port,
        reload=settings.debug,
        workers=1,  # Single worker for Leapcell
        log_level=settings.log_level.lower()
    )