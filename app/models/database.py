"""
SQLAlchemy database models
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class Store(Base):
    """Store model"""
    __tablename__ = "stores"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    # Scan settings
    scan_interval = Column(Integer, default=3600)  # seconds
    enabled = Column(Boolean, default=True)
    last_scan = Column(DateTime, nullable=True)
    next_scan = Column(DateTime, nullable=True)
    
    # Alert settings
    notify_low_stock = Column(Boolean, default=True)
    low_stock_threshold = Column(Integer, default=10)
    
    # Statistics
    total_products = Column(Integer, default=0)
    total_variants = Column(Integer, default=0)
    total_stock = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    scan_results = relationship("ScanResult", back_populates="store", cascade="all, delete-orphan")
    inventory_history = relationship("InventoryHistory", back_populates="store", cascade="all, delete-orphan")
    stock_alerts = relationship("StockAlert", back_populates="store", cascade="all, delete-orphan")
    webhooks = relationship("WebhookConfig", back_populates="store", cascade="all, delete-orphan")


class ScanResult(Base):
    """Scan result model"""
    __tablename__ = "scan_results"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    
    # Scan info
    success = Column(Boolean, nullable=False)
    error = Column(Text, nullable=True)
    scan_duration = Column(Float, nullable=True)
    
    # Statistics
    total_products = Column(Integer, default=0)
    valid_variants = Column(Integer, default=0)
    added_to_cart = Column(Integer, default=0)
    failed_to_add = Column(Integer, default=0)
    inventory_found = Column(Integer, default=0)
    total_stock = Column(Integer, default=0)
    
    # Data (JSON)
    products_data = Column(JSON, nullable=True)
    inventory_data = Column(JSON, nullable=True)
    
    # Timestamp
    timestamp = Column(DateTime, server_default=func.now())
    
    # Relationships
    store = relationship("Store", back_populates="scan_results")


class InventoryHistory(Base):
    """Inventory history model"""
    __tablename__ = "inventory_history"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    scan_result_id = Column(Integer, ForeignKey("scan_results.id"), nullable=True)
    
    # Product info
    product_id = Column(String(100), nullable=False, index=True)
    product_title = Column(String(500), nullable=False)
    variant_id = Column(String(100), nullable=False, index=True)
    variant_title = Column(String(500), nullable=False)
    
    # Inventory info
    stock = Column(Integer, nullable=False)
    price = Column(String(50), nullable=True)
    sku = Column(String(100), nullable=True)
    
    # Timestamp
    timestamp = Column(DateTime, server_default=func.now(), index=True)
    
    # Relationships
    store = relationship("Store", back_populates="inventory_history")


class StockAlert(Base):
    """Stock alert model"""
    __tablename__ = "stock_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    
    # Product info
    product_id = Column(String(100), nullable=False)
    product_title = Column(String(500), nullable=False)
    variant_id = Column(String(100), nullable=False)
    variant_title = Column(String(500), nullable=False)
    
    # Alert info
    alert_type = Column(String(50), nullable=False)  # low_stock, out_of_stock, back_in_stock
    current_stock = Column(Integer, nullable=False)
    threshold = Column(Integer, nullable=False)
    
    # Status
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    notified = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    store = relationship("Store", back_populates="stock_alerts")


class WebhookConfig(Base):
    """Webhook configuration model"""
    __tablename__ = "webhook_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    
    # Webhook settings
    url = Column(String(500), nullable=False)
    events = Column(JSON, nullable=False)  # List of event types
    enabled = Column(Boolean, default=True)
    secret = Column(String(255), nullable=True)
    
    # Statistics
    last_triggered = Column(DateTime, nullable=True)
    trigger_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    store = relationship("Store", back_populates="webhooks")


class APIKey(Base):
    """API key model for authentication"""
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Permissions
    is_active = Column(Boolean, default=True)
    permissions = Column(JSON, nullable=True)  # List of allowed endpoints/operations
    
    # Usage tracking
    last_used = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)