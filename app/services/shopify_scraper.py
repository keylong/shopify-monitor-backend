"""
Enhanced Shopify Scraper Service using cloudscraper
Robust and stable scraping with Cloudflare bypass
"""

import asyncio
import cloudscraper
import httpx
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
from selectolax.parser import HTMLParser
from loguru import logger
import orjson
from datetime import datetime


class ShopifyScraperService:
    """Advanced Shopify scraping service with multiple fallback strategies"""
    
    def __init__(self, store_url: str, use_proxy: Optional[str] = None):
        """
        Initialize scraper with store URL
        
        Args:
            store_url: Shopify store URL
            use_proxy: Optional proxy URL
        """
        self.store_url = store_url.rstrip('/')
        self.proxy = use_proxy
        
        # Primary scraper - cloudscraper for Cloudflare bypass
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'darwin',
                'desktop': True
            },
            delay=3  # Delay between retries
        )
        
        # Fallback - httpx for async requests
        self.async_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'application/json, text/html, */*',
                'Accept-Language': 'en-US,en;q=0.9',
            }
        )
        
        # State management
        self.products = []
        self.inventory_map = {}
        self.blacklist = set()  # Failed variant IDs
        self.session_cookies = None
        
    async def scan_inventory(self) -> Dict:
        """
        Execute complete inventory scan with multiple strategies
        
        Returns:
            Complete inventory data with stats
        """
        start_time = datetime.utcnow()
        logger.info(f"🚀 Starting inventory scan for {self.store_url}")
        
        try:
            # Step 1: Fetch products with retry logic
            products = await self._fetch_products_with_retry()
            if not products:
                return {"error": "Failed to fetch products", "success": False}
            
            # Step 2: Filter valid items
            valid_items = self._filter_available_items(products)
            logger.info(f"✅ Filtered {len(valid_items)} valid items from {len(products)} products")
            
            # Step 3: Clear cart
            await self._clear_cart()
            
            # Step 4: Batch add to cart with smart error handling
            added_count, failed_count = await self._smart_batch_add(valid_items)
            
            # Step 5: Extract inventory
            inventory = await self._extract_inventory()
            
            # Calculate statistics
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            
            result = {
                "success": True,
                "store_url": self.store_url,
                "timestamp": datetime.utcnow().isoformat(),
                "scan_duration": elapsed,
                "statistics": {
                    "total_products": len(products),
                    "valid_variants": len(valid_items),
                    "added_to_cart": added_count,
                    "failed_to_add": failed_count,
                    "inventory_found": len(inventory),
                    "total_stock": sum(inventory.values())
                },
                "products": self._process_products_data(products, inventory, valid_items),
                "inventory": inventory
            }
            
            logger.info(f"✅ Scan completed in {elapsed:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"❌ Scan failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        
    async def _fetch_products_with_retry(self, max_retries: int = 3) -> List[Dict]:
        """
        Fetch products with multiple strategies and retry logic
        """
        strategies = [
            self._fetch_with_cloudscraper,
            self._fetch_with_httpx,
            self._fetch_with_pagination
        ]
        
        for strategy in strategies:
            for attempt in range(max_retries):
                try:
                    logger.debug(f"Attempting {strategy.__name__} (attempt {attempt + 1})")
                    products = await strategy()
                    if products:
                        logger.info(f"✅ Successfully fetched {len(products)} products using {strategy.__name__}")
                        self.products = products
                        return products
                except Exception as e:
                    logger.warning(f"Strategy {strategy.__name__} failed: {e}")
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        logger.error("All strategies failed to fetch products")
        return []
    
    async def _fetch_with_cloudscraper(self) -> List[Dict]:
        """Strategy 1: Use cloudscraper for Cloudflare bypass"""
        url = f"{self.store_url}/products.json"
        params = {"limit": 250}
        
        if self.proxy:
            proxies = {"http": self.proxy, "https": self.proxy}
            response = self.scraper.get(url, params=params, proxies=proxies)
        else:
            response = self.scraper.get(url, params=params)
        
        response.raise_for_status()
        
        # Store cookies for session persistence
        self.session_cookies = response.cookies
        
        data = response.json()
        return data.get("products", [])
    
    async def _fetch_with_httpx(self) -> List[Dict]:
        """Strategy 2: Use async httpx client"""
        url = f"{self.store_url}/products.json"
        response = await self.async_client.get(url, params={"limit": 250})
        response.raise_for_status()
        
        data = response.json()
        return data.get("products", [])
    
    async def _fetch_with_pagination(self) -> List[Dict]:
        """Strategy 3: Fetch with pagination for large catalogs"""
        all_products = []
        page = 1
        
        while True:
            url = f"{self.store_url}/products.json"
            params = {"limit": 250, "page": page}
            
            response = self.scraper.get(url, params=params)
            if response.status_code != 200:
                break
                
            data = response.json()
            products = data.get("products", [])
            
            if not products:
                break
                
            all_products.extend(products)
            page += 1
            
            if len(products) < 250:  # Last page
                break
                
            await asyncio.sleep(0.5)  # Rate limiting
        
        return all_products
    
    def _filter_available_items(self, products: List[Dict]) -> List[Dict]:
        """
        Smart filtering of available items
        """
        valid_items = []
        
        for product in products:
            for variant in product.get("variants", [])[:10]:  # Limit variants per product
                # Skip if in blacklist
                if variant["id"] in self.blacklist:
                    continue
                
                # Check availability
                if not variant.get("available", False):
                    continue
                
                # Check inventory policy
                if (variant.get("inventory_management") and 
                    variant.get("inventory_policy") == "deny" and 
                    variant.get("inventory_quantity", 0) == 0):
                    continue
                
                valid_items.append({
                    "id": variant["id"],
                    "quantity": 1,
                    "product": product,
                    "variant": variant
                })
        
        return valid_items
    
    async def _clear_cart(self) -> bool:
        """Clear shopping cart"""
        try:
            response = self.scraper.post(f"{self.store_url}/cart/clear.js")
            return response.status_code == 200
        except:
            return False
    
    async def _smart_batch_add(self, items: List[Dict], batch_size: int = 100) -> Tuple[int, int]:
        """
        Smart batch addition with error recovery
        """
        added_count = 0
        failed_count = 0
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            # Filter blacklisted items
            batch = [item for item in batch if item["id"] not in self.blacklist]
            
            if not batch:
                continue
            
            cart_items = [{"id": item["id"], "quantity": 1} for item in batch]
            
            try:
                response = self.scraper.post(
                    f"{self.store_url}/cart/add.js",
                    json={"items": cart_items},
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    added_count += len(batch)
                elif response.status_code == 422:
                    # Handle 422 errors by identifying problem items
                    failed_count += await self._handle_422_error(batch, response)
                else:
                    failed_count += len(batch)
                    
            except Exception as e:
                logger.error(f"Batch add error: {e}")
                failed_count += len(batch)
            
            await asyncio.sleep(0.3)  # Rate limiting
        
        return added_count, failed_count
    
    async def _handle_422_error(self, batch: List[Dict], response) -> int:
        """Handle 422 errors intelligently"""
        try:
            error_data = response.json()
            error_msg = error_data.get("message", "")
            
            # Add problem items to blacklist
            for item in batch:
                product_name = f"{item['product']['title']} - {item['variant'].get('title', 'Default')}"
                if product_name in error_msg:
                    self.blacklist.add(item["id"])
                    logger.debug(f"Blacklisted: {product_name}")
            
            return len(batch)
        except:
            return len(batch)
    
    async def _extract_inventory(self) -> Dict[str, int]:
        """
        Extract inventory from cart page using multiple parsing methods
        """
        try:
            response = self.scraper.get(f"{self.store_url}/cart")
            html = response.text
            
            # Try fast parsing with selectolax first
            inventory = self._parse_with_selectolax(html)
            
            # Fallback to BeautifulSoup if needed
            if not inventory:
                inventory = self._parse_with_beautifulsoup(html)
            
            # Try cart.js API as last resort
            if not inventory:
                inventory = await self._get_from_cart_api()
            
            self.inventory_map = inventory
            return inventory
            
        except Exception as e:
            logger.error(f"Inventory extraction failed: {e}")
            return {}
    
    def _parse_with_selectolax(self, html: str) -> Dict[str, int]:
        """Fast HTML parsing with selectolax"""
        inventory = {}
        parser = HTMLParser(html)
        
        for input_tag in parser.css('input[type="number"]'):
            attrs = input_tag.attributes
            
            # Extract variant ID
            variant_id = (
                attrs.get("data-variant-id") or
                attrs.get("data-id") or
                attrs.get("id", "")
            )
            
            # Extract inventory
            max_stock = (
                attrs.get("max") or
                attrs.get("data-inventory-quantity") or
                attrs.get("data-max")
            )
            
            if variant_id and max_stock:
                # Extract numeric ID
                import re
                match = re.search(r'\d{10,}', str(variant_id))
                if match:
                    inventory[match.group()] = int(max_stock)
        
        return inventory
    
    def _parse_with_beautifulsoup(self, html: str) -> Dict[str, int]:
        """Fallback parsing with BeautifulSoup"""
        inventory = {}
        soup = BeautifulSoup(html, 'lxml')
        
        for input_tag in soup.find_all('input', {'type': 'number'}):
            variant_id = (
                input_tag.get("data-variant-id") or
                input_tag.get("data-id")
            )
            
            max_stock = (
                input_tag.get("max") or
                input_tag.get("data-inventory-quantity")
            )
            
            if variant_id and max_stock:
                inventory[str(variant_id)] = int(max_stock)
        
        return inventory
    
    async def _get_from_cart_api(self) -> Dict[str, int]:
        """Get inventory from cart.js API"""
        try:
            response = self.scraper.get(f"{self.store_url}/cart.js")
            cart_data = response.json()
            
            inventory = {}
            for item in cart_data.get("items", []):
                for field in ["inventory_quantity", "max_quantity", "available"]:
                    if field in item:
                        variant_id = str(item.get("variant_id", item.get("id")))
                        inventory[variant_id] = int(item[field])
                        break
            
            return inventory
        except:
            return {}
    
    def _process_products_data(self, products: List[Dict], inventory: Dict[str, int], 
                               valid_items: List[Dict]) -> List[Dict]:
        """Process and enrich product data"""
        valid_ids = {item["id"] for item in valid_items}
        processed = []
        
        for product in products:
            product_data = {
                "id": product["id"],
                "title": product["title"],
                "handle": product.get("handle"),
                "vendor": product.get("vendor"),
                "type": product.get("product_type"),
                "image": product.get("images", [{}])[0].get("src") if product.get("images") else None,
                "variants": [],
                "total_stock": 0,
                "in_stock_variants": 0,
                "out_of_stock_variants": 0
            }
            
            for variant in product.get("variants", []):
                variant_id = str(variant["id"])
                is_valid = variant["id"] in valid_ids
                stock = inventory.get(variant_id, 0) if is_valid else 0
                
                variant_data = {
                    "id": variant["id"],
                    "title": variant.get("title", "Default"),
                    "sku": variant.get("sku"),
                    "price": variant.get("price"),
                    "compare_at_price": variant.get("compare_at_price"),
                    "stock": stock,
                    "available": variant.get("available", False),
                    "is_valid": is_valid
                }
                
                product_data["variants"].append(variant_data)
                
                if is_valid:
                    product_data["total_stock"] += stock
                    if stock > 0:
                        product_data["in_stock_variants"] += 1
                    else:
                        product_data["out_of_stock_variants"] += 1
            
            processed.append(product_data)
        
        return processed
    
    async def close(self):
        """Clean up resources"""
        await self.async_client.aclose()