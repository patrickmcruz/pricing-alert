import logging
import json
import os
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Any
import httpx

from src.core.base_scraper import BaseScraper, SelectorOutdatedException
from src.core.contract import PriceContract, ProductSKU
from src.core.config import settings

logger = logging.getLogger(__name__)

class MercadoLivreScraper(BaseScraper):
    def __init__(self):
        super().__init__(store_name="mercado-livre", base_url="https://api.mercadolibre.com")
        self.app_id = settings.ml_app_id
        self.secret_key = settings.ml_secret_key
        self._access_token = None
        self._token_expires_at = 0.0

    async def _get_token(self) -> str:
        """Fetch or refresh the ML OAuth token."""
        now = datetime.now(timezone.utc).timestamp()
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        if not self.app_id or not self.secret_key:
            logger.error("[%s] Missing APP_ID or SECRET_KEY in environment variables.", self.store_name)
            return ""

        url = "https://api.mercadolibre.com/oauth/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.app_id,
            "client_secret": self.secret_key
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, data=data)
                resp.raise_for_status()
                token_data = resp.json()
                self._access_token = token_data.get("access_token")
                # Buffer of 60 seconds
                self._token_expires_at = now + token_data.get("expires_in", 21600) - 60
                logger.info("[%s] Successfully authenticated via API.", self.store_name)
                return self._access_token
        except Exception as e:
            logger.error("[%s] Failed to authenticate: %s", self.store_name, e)
            return ""

    def _extract_id(self, url: str) -> tuple[str, str]:
        """Returns (id_type, mlb_id). id_type is 'product' or 'item'."""
        # e.g. https://www.mercadolivre.com.br/placa-de-video-msi-geforce-rtx-5070/p/MLB51386368
        prod_match = re.search(r'/p/(MLB\d+)', url)
        if prod_match:
            return "product", prod_match.group(1)
            
        # e.g. https://produto.mercadolivre.com.br/MLB-4577606155-placa-de-video-pny...
        item_match = re.search(r'(MLB)-?(\d+)', url)
        if item_match:
            return "item", f"MLB{item_match.group(2)}"
            
        return "unknown", ""

    async def fetch(self, sku: ProductSKU, page: Any = None) -> str:
        """
        Fetches the JSON data using HTTPX from the ML API.
        We ignore `page` since we don't need Playwright.
        """
        logger.info("Fetching ML (API) for: %s", sku.product_url)
        
        token = await self._get_token()
        if not token:
            logger.error("[%s] Cannot fetch %s without API token.", self.store_name, sku.product_url)
            return ""

        id_type, mlb_id = self._extract_id(str(sku.product_url))
        if not mlb_id:
            logger.error("[%s] Could not extract ML ID from %s", self.store_name, sku.product_url)
            return ""

        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            async with httpx.AsyncClient() as client:
                if id_type == "product":
                    # For catalog products, we need the active items to get the actual prices
                    api_url = f"{self.base_url}/products/{mlb_id}/items"
                else:
                    api_url = f"{self.base_url}/items/{mlb_id}"
                    
                resp = await client.get(api_url, headers=headers)
                
                if resp.status_code == 404:
                    return json.dumps({"error": "not_found", "id_type": id_type})
                    
                resp.raise_for_status()
                data = resp.json()
                
                # We inject the id_type so parse() knows how to handle it
                return json.dumps({"id_type": id_type, "data": data})
                
        except Exception as e:
            logger.error("[%s] API fetch failed for %s: %s", self.store_name, sku.product_url, e)
            return ""

    def parse(self, document: str, sku: ProductSKU) -> Optional[PriceContract]:
        """
        Parses the ML JSON response.
        """
        if not document:
            return None

        try:
            payload = json.loads(document)
        except json.JSONDecodeError:
            return None

        if payload.get("error") == "not_found":
            return self._build_unavailable_contract(sku)

        id_type = payload.get("id_type")
        data = payload.get("data")
        
        price_cash = Decimal(0)
        price_installments = Decimal(0)
        installment_count = 1
        is_available = False

        if id_type == "product":
            results = data.get("results", [])
            if not results:
                return self._build_unavailable_contract(sku)
                
            # Filter active items
            active_items = [i for i in results if i.get("price")]
            if not active_items:
                return self._build_unavailable_contract(sku)
                
            # Find the lowest price item
            best_item = min(active_items, key=lambda x: float(x["price"]))
            
            price_cash = Decimal(str(best_item["price"]))
            
            # Estimate installments based on listing type
            # gold_pro usually offers up to 10x without interest
            listing_type = best_item.get("listing_type_id", "")
            if listing_type == "gold_pro":
                price_installments = price_cash
                installment_count = 10
            else:
                price_installments = price_cash
                installment_count = 1
                
            is_available = True

        elif id_type == "item":
            if data.get("status") != "active":
                return self._build_unavailable_contract(sku)
                
            price = data.get("price")
            if not price:
                return self._build_unavailable_contract(sku)
                
            price_cash = Decimal(str(price))
            
            listing_type = data.get("listing_type_id", "")
            if listing_type == "gold_pro":
                price_installments = price_cash
                installment_count = 10
            else:
                price_installments = price_cash
                installment_count = 1
                
            is_available = True

        return PriceContract(
            product_url=sku.product_url,
            store_name=self.store_name,
            search_keyword=sku.search_keyword,
            brand=sku.brand,
            model=sku.model,
            product_title=sku.product_title,
            price_cash=price_cash,
            price_installments=price_installments,
            installment_count=installment_count,
            scraped_at=datetime.now(timezone.utc),
            parser_version="v2 (API)",
            currency="BRL",
            is_available=is_available,
        )

    def _build_unavailable_contract(self, sku: ProductSKU) -> PriceContract:
        return PriceContract(
            product_url=sku.product_url,
            store_name=self.store_name,
            search_keyword=sku.search_keyword,
            brand=sku.brand,
            model=sku.model,
            product_title=sku.product_title,
            price_cash=Decimal(0),
            price_installments=Decimal(0),
            installment_count=0,
            scraped_at=datetime.now(timezone.utc),
            parser_version="v2 (API)",
            currency="BRL",
            is_available=False,
        )
