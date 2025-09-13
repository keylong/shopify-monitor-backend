"""
Pydantic schemas for request/response validation
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from enum import Enum


class ScanStatus(str, Enum):
    """Scan status enum"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StoreBase(BaseModel):
    """Base store schema"""
    name: str = Field(..., min_length=1, max_length=100)
    url: HttpUrl
    description: Optional[str] = None
    scan_interval: int = Field(default=3600, ge=300)  # Min 5 minutes
    enabled: bool = True
    notify_low_stock: bool = True
    low_stock_threshold: int = Field(default=10, ge=0)
    
    class Config:
        json_encoders = {
            HttpUrl: str
        }


class StoreCreate(StoreBase):
    """Store creation schema"""
    pass


class StoreUpdate(BaseModel):
    """Store update schema"""
    name: Optional[str] = None
    description: Optional[str] = None
    scan_interval: Optional[int] = None
    enabled: Optional[bool] = None
    notify_low_stock: Optional[bool] = None
    low_stock_threshold: Optional[int] = None


class Store(StoreBase):
    """Store response schema"""
    id: int
    created_at: datetime
    updated_at: datetime
    last_scan: Optional[datetime] = None
    next_scan: Optional[datetime] = None
    total_products: int = 0
    total_variants: int = 0
    total_stock: int = 0
    
    class Config:
        from_attributes = True


class VariantInfo(BaseModel):
    """Variant information schema"""
    id: str
    title: str
    sku: Optional[str] = None
    price: Optional[str] = None
    compare_at_price: Optional[str] = None
    stock: int = 0
    available: bool = True
    is_valid: bool = True


class ProductInfo(BaseModel):
    """Product information schema"""
    id: str
    title: str
    handle: Optional[str] = None
    vendor: Optional[str] = None
    type: Optional[str] = None
    image: Optional[str] = None
    variants: List[VariantInfo] = []
    total_stock: int = 0
    in_stock_variants: int = 0
    out_of_stock_variants: int = 0


class ScanStatistics(BaseModel):
    """Scan statistics schema"""
    total_products: int = 0
    valid_variants: int = 0
    added_to_cart: int = 0
    failed_to_add: int = 0
    inventory_found: int = 0
    total_stock: int = 0


class ScanRequest(BaseModel):
    """Manual scan request schema"""
    store_url: HttpUrl
    use_proxy: Optional[str] = None
    save_results: bool = True


class ScanResult(BaseModel):
    """Scan result schema"""
    id: Optional[int] = None
    store_id: Optional[int] = None
    store_url: str
    success: bool
    error: Optional[str] = None
    timestamp: datetime
    scan_duration: Optional[float] = None
    statistics: Optional[ScanStatistics] = None
    products: List[ProductInfo] = []
    inventory: Dict[str, int] = {}
    
    class Config:
        from_attributes = True


class InventoryHistory(BaseModel):
    """Inventory history schema"""
    id: int
    store_id: int
    product_id: str
    product_title: str
    variant_id: str
    variant_title: str
    stock: int
    price: Optional[str] = None
    timestamp: datetime
    
    class Config:
        from_attributes = True


class StockAlert(BaseModel):
    """Stock alert schema"""
    id: int
    store_id: int
    product_title: str
    variant_title: str
    current_stock: int
    threshold: int
    alert_type: str  # "low_stock", "out_of_stock", "back_in_stock"
    created_at: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    """Dashboard statistics schema"""
    total_stores: int = 0
    active_stores: int = 0
    total_products: int = 0
    total_variants: int = 0
    total_stock: int = 0
    low_stock_items: int = 0
    out_of_stock_items: int = 0
    recent_scans: int = 0
    failed_scans: int = 0
    average_scan_time: float = 0


class ExportRequest(BaseModel):
    """Export request schema"""
    store_id: Optional[int] = None
    format: str = Field(default="csv", pattern="^(csv|json|excel)$")
    include_history: bool = False
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class WebhookConfig(BaseModel):
    """Webhook configuration schema"""
    id: Optional[int] = None
    store_id: int
    url: HttpUrl
    events: List[str] = ["low_stock", "out_of_stock"]
    enabled: bool = True
    secret: Optional[str] = None
    
    class Config:
        from_attributes = True


class APIResponse(BaseModel):
    """Standard API response"""
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None
    errors: Optional[List[str]] = None