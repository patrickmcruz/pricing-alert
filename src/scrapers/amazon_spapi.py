"""
Dormant Amazon Selling Partner API (SP-API) pricing client - NOT registered
as a scraper (no @register_scraper), so it plays no part in orchestration.

Product Pricing API v0's getItemOffers works for arbitrary ASINs, but reaching
it requires a *production* refresh_token obtained via self-authorization in
Seller Central, which in turn requires an active Amazon seller account - not
just LWA app credentials. Without one, this can only reach the SP-API sandbox
(static mock data for undocumented test ASINs, not real prices), so the
active "amazon" scraper (src/scrapers/amazon.py) is a direct Playwright/HTML
scraper instead, like kabum.py/terabyte.py.

Kept here in case production seller access becomes available later - see
scripts/discover_amazon_catalog.py, which still uses this class to search the
SP-API Catalog Items API for ASINs.
"""
import logging
import re
import json
from decimal import Decimal
from typing import ClassVar, Optional
from datetime import datetime, timezone

import httpx

from src.core.base_scraper import BaseScraper
from src.core.contract import PriceContract, ProductSKU
from src.core.config import settings
from src.core.contract_factory import build_price_contract, build_unavailable_contract

logger = logging.getLogger(__name__)

_ASIN_RE = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})", re.I)


class AmazonSPAPIScraper(BaseScraper):
    """
    Scraper implementation for Amazon.com.br using the Selling Partner API
    (Product Pricing API v0 - getItemOffers). Dormant: see module docstring.
    """

    # Pure JSON/REST integration - no browser needed, so PriceEngine injects
    # an httpx.AsyncClient (via HTTPClientFactory) instead of a Playwright Page.
    transport_type: ClassVar[str] = "http"

    def __init__(self):
        base_url = settings.amazon_spapi_sandbox_base_url if settings.amazon_spapi_sandbox else settings.amazon_spapi_base_url
        super().__init__(store_name="amazon", base_url=base_url)
        self._access_token = None
        self._token_expires_at = 0

    async def _get_access_token(self, client: httpx.AsyncClient) -> Optional[str]:
        """Fetches or returns a cached LWA access token, exchanged from the stored refresh_token."""
        now = datetime.now(timezone.utc).timestamp()
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        if not settings.amazon_lwa_client_id or not settings.amazon_lwa_client_secret:
            logger.error(
                "[%s] Missing LWA credentials in settings (AMAZON_LWA_APP_CLIENT_ID/SECRET_KEY)",
                self.store_name,
            )
            return None

        # Sandbox and production refresh tokens are minted separately in Seller Central and
        # are not interchangeable - each only authenticates against its matching host.
        refresh_token = (
            settings.amazon_sp_api_sandbox_refresh_token
            if settings.amazon_spapi_sandbox
            else settings.amazon_sp_api_refresh_token
        )
        if not refresh_token:
            logger.error(
                "[%s] Missing %s - see Seller Central's authorization/sandbox-token page.",
                self.store_name,
                "AMAZON_SP_API_SANDBOX_REFRESH_TOKEN" if settings.amazon_spapi_sandbox else "AMAZON_SP_API_REFRESH_TOKEN",
            )
            return None

        try:
            response = await client.post(
                "https://api.amazon.com/auth/o2/token",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": settings.amazon_lwa_client_id,
                    "client_secret": settings.amazon_lwa_client_secret,
                },
            )

            if response.status_code != 200:
                logger.error("[%s] Failed to authenticate: %s", self.store_name, response.text)
                return None

            data = response.json()
            self._access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            self._token_expires_at = now + expires_in - 300  # 5 min buffer
            logger.info("[%s] Successfully authenticated with SP-API.", self.store_name)
            return self._access_token

        except Exception as e:
            logger.error("[%s] Error fetching SP-API token: %s", self.store_name, e)
            return None

    def _extract_asin_from_url(self, url: str) -> Optional[str]:
        """Extracts the ASIN (e.g. B0DXXXXXX) from a /dp/ or /gp/product/ Amazon URL."""
        match = _ASIN_RE.search(url)
        return match.group(1).upper() if match else None

    async def fetch(self, sku: ProductSKU, client: httpx.AsyncClient) -> str:
        """
        Retrieves the offers JSON for the SKU's ASIN from the Product Pricing API.
        """
        token = await self._get_access_token(client)
        if not token:
            return ""

        asin = self._extract_asin_from_url(str(sku.product_url))
        if not asin:
            logger.error("[%s] Could not extract ASIN from URL: %s", self.store_name, sku.product_url)
            return ""

        headers = {
            "x-amz-access-token": token,
            "Content-Type": "application/json",
        }

        try:
            response = await client.get(
                f"{self.base_url}/products/pricing/v0/items/{asin}/offers",
                headers=headers,
                params={
                    "MarketplaceId": settings.amazon_marketplace_id,
                    "ItemCondition": "New",
                },
            )

            if response.status_code != 200:
                logger.error(
                    "[%s] Pricing API returned %s for %s: %s",
                    self.store_name,
                    response.status_code,
                    asin,
                    response.text,
                )
                return ""

            return response.text

        except Exception as e:
            logger.error("[%s] Error fetching pricing data for %s: %s", self.store_name, sku.product_url, e)
            return ""

    def parse(self, document: str, sku: ProductSKU) -> Optional[PriceContract]:
        """
        Parses the getItemOffers JSON response into a PriceContract.
        """
        if not document:
            return None

        try:
            data = json.loads(document)
        except json.JSONDecodeError:
            logger.error("[%s] Failed to parse JSON document.", self.store_name)
            return None

        parser_version = f"{self.store_name}_spapi_v1"
        payload = data.get("payload", {})
        offers = payload.get("Offers", [])

        if not offers:
            return build_unavailable_contract(self, sku, parser_version=parser_version)

        landed_prices = []
        for offer in offers:
            listing_price = offer.get("ListingPrice", {}).get("Amount")
            shipping_price = offer.get("Shipping", {}).get("Amount", 0)
            if listing_price is None:
                continue
            landed_prices.append(Decimal(str(listing_price)) + Decimal(str(shipping_price)))

        if not landed_prices:
            return build_unavailable_contract(self, sku, parser_version=parser_version)

        price_cash = min(landed_prices)

        return build_price_contract(
            self,
            sku,
            price_cash=price_cash,
            product_title=sku.product_title,
            parser_version=parser_version,
            is_available=True,
        )
