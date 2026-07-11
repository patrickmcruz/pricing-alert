import logging
import re
import json
import asyncio
from decimal import Decimal
from typing import Any, Optional
from datetime import datetime, timezone
import urllib.parse

from src.core.base_scraper import BaseScraper, SelectorOutdatedException
from src.core.contract import PriceContract, ProductSKU
from src.core.config import settings

logger = logging.getLogger(__name__)

class MercadoLivreScraper(BaseScraper):
    """
    Scraper implementation for Mercado Livre using the Official API.
    Bypasses WAF/Captcha by authenticating as a Developer.
    """

    def __init__(self):
        super().__init__(store_name="mercado-livre", base_url="https://api.mercadolibre.com")
        self._access_token = None
        self._token_expires_at = 0

    async def _get_access_token(self, client: Any) -> Optional[str]:
        """Fetches or returns cached OAuth token using client.request."""
        now = datetime.now(timezone.utc).timestamp()
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        if not settings.ml_app_id or not settings.ml_secret_key:
            logger.error("[%s] Missing API credentials in settings (MERCADOLIVRE_APP_ID/SECRET)", self.store_name)
            return None

        try:
            # Playwright client APIRequestContext
            response = await client.request.post(
                "https://api.mercadolibre.com/oauth/token",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.ml_app_id,
                    "client_secret": settings.ml_secret_key
                }
            )
            
            if response.status != 200:
                logger.error("[%s] Failed to authenticate: %s", self.store_name, await response.text())
                return None
                
            data = await response.json()
            self._access_token = data.get("access_token")
            expires_in = data.get("expires_in", 21600)  # usually 6 hours
            self._token_expires_at = now + expires_in - 300  # 5 min buffer
            logger.info("[%s] Successfully authenticated with ML API.", self.store_name)
            return self._access_token
            
        except Exception as e:
            logger.error("[%s] Error fetching ML token: %s", self.store_name, e)
            return None

    def _extract_id_from_url(self, url: str) -> Optional[str]:
        """Extracts the catalog product ID (e.g., MLB123) from the URL."""
        # e.g., /p/MLB53508354
        match = re.search(r'/p/(MLB\d+)', url)
        if match:
            return match.group(1)
        # fallback for normal items e.g., /MLB-123456- or /MLB123456
        match = re.search(r'(MLB-?\d+)', url)
        if match:
            return match.group(1).replace("-", "")
        return None

    async def fetch(self, sku: ProductSKU, client: Any) -> str:
        """
        Retrieves the JSON data from the ML API using Playwright's API context.
        """
        token = await self._get_access_token(client)
        if not token:
            return ""

        product_id = self._extract_id_from_url(str(sku.product_url))
        if not product_id:
            logger.error("[%s] Could not extract ID from URL: %s", self.store_name, sku.product_url)
            return ""

        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            # Depending on if it's a catalog product or an item listing
            # Most of our targets are Catalog Products (starts with /p/)
            is_catalog = "/p/" in str(sku.product_url)
            
            if is_catalog:
                # 1. Fetch catalog product details
                prod_resp = await client.request.get(f"https://api.mercadolibre.com/products/{product_id}", headers=headers)
                if prod_resp.status != 200:
                    logger.error("[%s] Product API returned %s: %s", self.store_name, prod_resp.status, await prod_resp.text())
                    return ""
                
                prod_data = await prod_resp.json()
                
                # 2. Fetch active items for this catalog product
                items_resp = await client.request.get(f"https://api.mercadolibre.com/products/{product_id}/items", headers=headers)
                items_data = await items_resp.json() if items_resp.status == 200 else {"results": []}
                
                # Combine data to pass to parse()
                combined_data = {
                    "type": "catalog",
                    "product": prod_data,
                    "items": items_data.get("results", [])
                }
                return json.dumps(combined_data)
                
            else:
                # Direct item listing fallback
                item_resp = await client.request.get(f"https://api.mercadolibre.com/items/{product_id}", headers=headers)
                if item_resp.status != 200:
                    logger.error("[%s] Item API returned %s", self.store_name, item_resp.status)
                    return ""
                    
                item_data = await item_resp.json()
                combined_data = {
                    "type": "item",
                    "item": item_data
                }
                return json.dumps(combined_data)
                
        except Exception as e:
            logger.error("[%s] Error fetching API data for %s: %s", self.store_name, sku.product_url, e)
            return ""

    def parse(self, document: str, sku: ProductSKU) -> Optional[PriceContract]:
        """
        Parses the JSON document returned by the API.
        """
        if not document:
            return None
            
        try:
            data = json.loads(document)
        except json.JSONDecodeError:
            logger.error("[%s] Failed to parse JSON document.", self.store_name)
            return None

        if data.get("type") == "catalog":
            return self._parse_catalog(data, sku)
        elif data.get("type") == "item":
            return self._parse_item(data, sku)
            
        return None

    def _parse_catalog(self, data: dict, sku: ProductSKU) -> PriceContract:
        prod = data.get("product", {})
        items = data.get("items", [])
        
        title = prod.get("name", sku.product_title)
        
        if not items:
            return self._build_unavailable_contract(sku, title)
            
        # In Mercado Livre:
        # gold_special / gold: Usually classic listings (cash price / interest on installments)
        # gold_pro: Usually premium listings (interest-free installments, so it's the "installment price" baseline)
        
        # We find the lowest price overall for Cash Price
        lowest_cash = min([Decimal(str(item.get("price", 0))) for item in items if item.get("price")])
        
        # We find the lowest price in 'gold_pro' listings for the Installment Price
        pro_items = [Decimal(str(item.get("price", 0))) for item in items if item.get("listing_type_id") == "gold_pro" and item.get("price")]
        
        price_cash = lowest_cash
        price_installments = min(pro_items) if pro_items else price_cash
        
        # ML usually offers 10x or 12x on gold_pro. 
        # API doesn't detail exact max installments in the items array directly, but it's universally 10 for electronics now or 12.
        # If it's a pro listing, we'll assume 10x max as per ML standard for electronics, or 1x if no pro listing exists.
        installment_count = 10 if pro_items else 1
        
        discount = None
        if price_installments and price_installments > 0 and price_cash > 0:
            discount = price_installments - price_cash

        return PriceContract(
            store_name=self.store_name,
            search_keyword=sku.search_keyword,
            product_title=title,
            product_url=sku.product_url,
            price_cash=price_cash,
            price_installments=price_installments,
            installment_count=installment_count,
            currency="BRL",
            parser_version=f"{self.store_name}_api_v1",
            is_available=True,
            brand=sku.brand,
            model=sku.model,
            discount=discount
        )

    def _parse_item(self, data: dict, sku: ProductSKU) -> PriceContract:
        item = data.get("item", {})
        title = item.get("title", sku.product_title)
        
        status = item.get("status")
        qty = item.get("available_quantity", 0)
        
        if status != "active" or qty <= 0:
            return self._build_unavailable_contract(sku, title)
            
        price = Decimal(str(item.get("price", 0)))
        if price <= 0:
            return self._build_unavailable_contract(sku, title)
            
        listing_type = item.get("listing_type_id")
        
        if listing_type == "gold_pro":
            price_installments = price
            # Without detailed parsing of the item's body, we can't be sure of cash discount.
            price_cash = price 
            installment_count = 10
        else:
            price_cash = price
            price_installments = price
            installment_count = 1
            
        return PriceContract(
            store_name=self.store_name,
            search_keyword=sku.search_keyword,
            product_title=title,
            product_url=sku.product_url,
            price_cash=price_cash,
            price_installments=price_installments,
            installment_count=installment_count,
            currency="BRL",
            parser_version=f"{self.store_name}_api_v1",
            is_available=True,
            brand=sku.brand,
            model=sku.model,
            discount=0
        )

    def _build_unavailable_contract(self, sku: ProductSKU, title: str = None) -> PriceContract:
        return PriceContract(
            product_url=sku.product_url,
            store_name=self.store_name,
            search_keyword=sku.search_keyword,
            brand=sku.brand,
            model=sku.model,
            product_title=title or sku.product_title,
            price_cash=Decimal(0),
            price_installments=Decimal(0),
            installment_count=0,
            scraped_at=datetime.now(timezone.utc),
            parser_version="api_v1",
            currency="BRL",
            is_available=False,
        )
