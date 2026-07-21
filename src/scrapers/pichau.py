import json
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from bs4 import BeautifulSoup

from src.core.base_scraper import BaseScraper, SelectorOutdatedException, StoreUnavailableException
from src.core.config import settings
from src.core.contract import PriceContract, ProductSKU
from src.core.contract_factory import build_price_contract
from src.core.parsing_utils import clean_brl_price, compute_discount, has_maintenance_marker_in_html
from src.core.registry import register_scraper

logger = logging.getLogger(__name__)

# pichau.com.br is a Next.js storefront over an Adobe Commerce (Magento)
# GraphQL backend. Product data isn't rendered as scrapeable DOM elements -
# the HTML response embeds the full GraphQL product payload as JSON inside
# `self.__next_f.push([id, "..."])` calls (Next.js's React Server Component
# streaming format), the same on both product pages and search result pages.
# So there is no CSS-selector layer for this store at all - once fetched,
# parsing is JSON extraction, not DOM selection.
#
# Fetching still goes through Playwright (transport_type stays "browser",
# the BaseScraper default), same as Kabum/Terabyte: a plain httpx GET gets a
# 403 from Cloudflare - fronting the origin - serving a decoy page styled
# exactly like a real "Site em Manutenção" maintenance page (same title
# text this store's maintenance-detection was originally built around, see
# spec §4), while a real Chromium session via BrowserFactory gets the
# genuine page every time. Confirmed directly against the live site during
# this store's onboarding: httpx -> 403 decoy, Playwright -> 200 real page
# with the embedded JSON described above.
#
# Each push() argument is itself a JSON array `[id, "<escaped RSC text>"]`;
# decoding it once un-escapes the inner text into real JSON syntax. From
# there, `_PRODUCT_ANCHOR_RE` finds each product object's start and
# `json.JSONDecoder.raw_decode` reads exactly one balanced value from that
# position - robust to whatever wraps it (arrays, other RSC objects) without
# needing to know the surrounding structure.
_PUSH_ARG_RE = re.compile(r'self\.__next_f\.push\((\[\d+,"(?:[^"\\]|\\.)*"\])\)')
_PRODUCT_ANCHOR_RE = re.compile(r'\{"id":\d+,"sku":"')


def extract_pichau_products(html: str) -> list[dict]:
    """
    Extracts every distinct GraphQL product object embedded in a Pichau page
    (product page: one; search results page: one per listed product).
    Deterministic, pure, no network I/O - shared by PichauScraper.parse() and
    scripts/discover_pichau_gpus.py.
    """
    decoder = json.JSONDecoder()
    seen_skus: set[str] = set()
    products: list[dict] = []

    for push_match in _PUSH_ARG_RE.finditer(html):
        try:
            _, payload = json.loads(push_match.group(1))
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(payload, str):
            continue

        for anchor_match in _PRODUCT_ANCHOR_RE.finditer(payload):
            try:
                obj, _ = decoder.raw_decode(payload, anchor_match.start())
            except json.JSONDecodeError:
                continue
            sku = obj.get("sku")
            # "pichau_prices" filters out incomplete cross-references to a
            # product (e.g. related-product stubs) that carry only id/sku.
            if sku and sku not in seen_skus and "pichau_prices" in obj:
                seen_skus.add(sku)
                products.append(obj)

    return products


def _url_key_from_url(product_url: str) -> str:
    return product_url.rstrip("/").rsplit("/", 1)[-1]


def _to_decimal(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _extract_brand_and_model(product: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    brand = None
    model = None

    marcas_info = product.get("marcas_info")
    if isinstance(marcas_info, dict):
        brand = marcas_info.get("name") or marcas_info.get("brand")

    if not brand:
        brand = product.get("brand")

    specs = product.get("specifications")
    if isinstance(specs, list):
        for spec in specs:
            if not isinstance(spec, dict):
                continue
            name = str(spec.get("name") or "").strip().lower()
            value = str(spec.get("value") or "").strip()
            if not value:
                continue
            if name in {"modelo", "model", "variant"}:
                model = value
                break

    if not model:
        model = product.get("model")

    if isinstance(brand, str):
        brand = brand.strip() or None
    if isinstance(model, str):
        model = model.strip() or None

    return brand, model


def _extract_installment_data_from_dom(document: str) -> tuple[Optional[Decimal], Optional[int]]:
    soup = BeautifulSoup(document, "lxml")

    selectors = [
        "#main-content > div > div.MuiContainer-root.MuiContainer-maxWidthXl.mui-iunmvg-top > div > div.MuiGrid2-root.MuiGrid2-direction-xs-row.MuiGrid2-grid-xs-12.MuiGrid2-grid-sm-5.mui-1oj8u1k-gridInfo > div.mui-caclr-sectionWrapperHorizontal-extraSpace > div:nth-child(3) > div > div.mui-7ie9un-price_total",
        "div.mui-7ie9un-price_total",
    ]
    price_elem = None
    for selector in selectors:
        price_elem = soup.select_one(selector)
        if price_elem is not None:
            break

    count_elem = None
    if price_elem is not None:
        for candidate in [price_elem] + list(price_elem.parents):
            if candidate is None:
                continue
            span = candidate.select_one("span")
            if span is not None:
                count_elem = span
                break
    if count_elem is None:
        count_elem = soup.select_one(
            "#main-content > div > div.MuiContainer-root.MuiContainer-maxWidthXl.mui-iunmvg-top > div > div.MuiGrid2-root.MuiGrid2-direction-xs-row.MuiGrid2-grid-xs-12.MuiGrid2-grid-sm-5.mui-1oj8u1k-gridInfo > div.mui-caclr-sectionWrapperHorizontal-extraSpace > div:nth-child(3) > div > span"
        )

    if price_elem is None and count_elem is None:
        return None, None

    price_installments = clean_brl_price(price_elem.get_text(" ", strip=True) if price_elem else None)

    installment_count = None
    if count_elem is not None:
        count_text = count_elem.get_text(" ", strip=True)
        match = re.search(r"(\d+)", count_text)
        if match:
            installment_count = int(match.group(1))

    return price_installments, installment_count


@register_scraper
class PichauScraper(BaseScraper):
    """
    Scraper implementation for Pichau (pichau.com.br). Playwright fetch
    (Cloudflare blocks plain HTTP clients - see module docstring above),
    embedded-JSON parse (see extract_pichau_products above) - no CSS
    selectors, unlike KabumScraper/TerabyteScraper.
    """

    def __init__(self):
        super().__init__(store_name="pichau", base_url="https://www.pichau.com.br")

    async def fetch(self, sku: ProductSKU, client: Any) -> str:
        """
        Retrieves the raw HTML document from the store using Playwright.
        """
        try:
            await client.goto(
                str(sku.product_url), wait_until="networkidle", timeout=settings.navigation_timeout_ms
            )
            return await client.content()
        except Exception as e:
            logger.error("[%s] Network fetch failed for %s: %s", self.store_name, sku.product_url, e)
            return ""

    def parse(self, document: str, sku: ProductSKU) -> Optional[PriceContract]:
        """
        Parses the Pichau product page's embedded product JSON.
        """
        parser_version = "pichau_v2"

        if has_maintenance_marker_in_html(document):
            raise StoreUnavailableException(f"[{self.store_name}] Store appears to be down for maintenance.")

        products = extract_pichau_products(document)
        if not products:
            raise SelectorOutdatedException(
                f"[{self.store_name}] No embedded product JSON found for {sku.product_url}."
            )

        target_url_key = _url_key_from_url(str(sku.product_url))
        product = next((p for p in products if p.get("url_key") == target_url_key), products[0])

        title = product.get("name") or sku.product_title
        brand, model = _extract_brand_and_model(product)
        prices = product.get("pichau_prices") or {}

        price_cash = _to_decimal(prices.get("avista"))
        if price_cash is None or price_cash <= 0:
            return None

        price_installments = _to_decimal(prices.get("base_price"))
        installment_count = prices.get("max_installments")

        dom_price_installments, dom_installment_count = _extract_installment_data_from_dom(document)
        if dom_price_installments is not None:
            price_installments = dom_price_installments
        if dom_installment_count is not None:
            installment_count = dom_installment_count

        is_available = product.get("stock_status") == "IN_STOCK"

        contract = build_price_contract(
            self,
            sku,
            price_cash=price_cash,
            price_installments=price_installments,
            installment_count=installment_count,
            product_title=title,
            parser_version=parser_version,
            is_available=is_available,
            discount=compute_discount(price_cash, price_installments),
        )

        return contract.model_copy(update={"brand": brand, "model": model})
