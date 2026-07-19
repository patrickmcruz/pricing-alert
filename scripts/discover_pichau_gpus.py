"""Search-grid discovery for Pichau: crawls the store's search results for
RTX 5070 / RTX 5070 Ti and upserts any new matches into data/target_urls.json
- the same manifest DiscoveryEngine/migrate_target_urls.py already treat as
the source of truth for tracked SKUs.

Deliberately NOT wired into DiscoveryEngine or the orchestrator boot
sequence - see specs/pichau-scraper/spec.md §3 for why. Run manually
whenever you want to pick up new Pichau listings:

    python scripts/discover_pichau_gpus.py

Pichau's search results page embeds the full product list as JSON inside
the page's `self.__next_f.push(...)` script tags (Next.js RSC streaming) -
see src.scrapers.pichau.extract_pichau_products for how that's parsed.
Fetching still goes through Playwright: a plain HTTP client gets a 403 from
Cloudflare (serving a decoy page styled like a real maintenance page - see
specs/pichau-scraper/spec.md §4), while a real Chromium session gets the
genuine page every time.

The network fetch (Playwright) and the grid-parsing logic are split the
same way BaseScraper.fetch()/parse() are, for the same reason: parsing is
pure and deterministic, so it's unit-testable against a static HTML fixture
without ever touching a real browser (see
tests/unit/test_discover_pichau_gpus.py).
"""
import asyncio
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation
from typing import Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.base_scraper import StoreUnavailableException
from src.core.browser import BrowserFactory
from src.core.config import settings
from src.core.parsing_utils import has_maintenance_marker_in_html
from src.scrapers.pichau import extract_pichau_products

TARGET_URLS_PATH = settings.target_urls_path
BASE_URL = "https://www.pichau.com.br"

SEARCH_URLS = {
    # product_category=6459 (GPUs) + rgpu=<facet id> is Pichau's exact GPU-model
    # filter, not just a free-text query - narrower and more reliable than the
    # plain ?q= search used during early exploration of this store.
    "rtx 5070": "https://www.pichau.com.br/search?q=5070&product_category=6459&rgpu=7725",
    "rtx 5070 ti": "https://www.pichau.com.br/search?q=5070&product_category=6459&rgpu=7726",
}

# "5070 T.I" (the literal query string) vs. "5070ti"/"5070 ti" as it
# typically appears in a real product title - normalize both to the same
# chipset key DiscoveryEngine._resolve_chipset_name would resolve to.
_TI_RE = re.compile(r"5070\s*t\.?\s*i\b", re.IGNORECASE)
_PLAIN_RE = re.compile(r"\b5070\b(?!\s*t\.?\s*i)", re.IGNORECASE)


def _matches_chipset(title: str, search_keyword: str) -> bool:
    if search_keyword == "rtx 5070 ti":
        return bool(_TI_RE.search(title))
    return bool(_PLAIN_RE.search(title))


def _to_decimal(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def parse_search_results(html: str, search_keyword: str) -> list[dict]:
    """
    Pure parsing: extracts candidate products from a search-results page's
    HTML that match the target chipset. No network I/O - unit-testable
    against a static fixture, same contract as every scraper's parse().
    """
    # Checked first, same reasoning as PichauScraper.parse(): a maintenance
    # page has zero embedded products for the same reason a real page whose
    # markup has drifted would - telling the two apart here is what stops
    # this script from reporting a misleading "0 candidates found" when the
    # store is just down.
    if has_maintenance_marker_in_html(html):
        raise StoreUnavailableException("[pichau] Store appears to be down for maintenance.")

    found = []
    for product in extract_pichau_products(html):
        title = product.get("name") or ""
        if not _matches_chipset(title, search_keyword):
            continue

        url_key = product.get("url_key")
        if not url_key:
            continue

        brand = ((product.get("marcas_info") or {}).get("name")) or None
        price_cash = _to_decimal((product.get("pichau_prices") or {}).get("avista"))

        found.append({
            "store_name": "pichau",
            "search_keyword": search_keyword,
            "product_url": f"{BASE_URL}/{url_key}",
            "brand": brand,
            "model": None,
            "product_title": title,
            "_discovered_price_cash": price_cash,  # informational only, not part of the manifest schema
        })
    return found


def _load_existing_manifest() -> list[dict]:
    if not os.path.exists(TARGET_URLS_PATH):
        return []
    with open(TARGET_URLS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


async def discover() -> None:
    factory = BrowserFactory()
    existing = _load_existing_manifest()
    existing_urls = {row["product_url"] for row in existing}

    all_found: list[dict] = []
    store_unavailable = False
    page = await factory.create(scraper=None)
    try:
        for search_keyword, url in SEARCH_URLS.items():
            print(f"Searching {search_keyword!r} at {url} ...")
            await page.goto(url, wait_until="networkidle", timeout=settings.navigation_timeout_ms)
            html = await page.content()
            try:
                found = parse_search_results(html, search_keyword)
            except StoreUnavailableException:
                # Reported once at the end, not raised - one query being down
                # shouldn't stop the other from still being checked.
                print("  -> pichau.com.br appears to be down for maintenance right now.")
                store_unavailable = True
                continue
            print(f"  -> {len(found)} matching product(s) found on the results page.")
            all_found.extend(found)
    finally:
        await factory.close(page)

    if store_unavailable and not all_found:
        print(
            "\nAborted: pichau.com.br was down for every search query. Not touching "
            f"{TARGET_URLS_PATH} - re-run this script once the site is back."
        )
        return

    new_rows = []
    seen_this_run = set()
    for row in all_found:
        if row["product_url"] in existing_urls or row["product_url"] in seen_this_run:
            continue
        seen_this_run.add(row["product_url"])
        row.pop("_discovered_price_cash", None)  # not part of the manifest schema
        new_rows.append(row)

    if new_rows:
        merged = existing + new_rows
        with open(TARGET_URLS_PATH, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)

    print(
        f"\nDone. {len(all_found)} candidate(s) found, {len(new_rows)} new, "
        f"{len(all_found) - len(new_rows)} already tracked. "
        f"{'Wrote ' + str(len(new_rows)) + ' row(s) to ' + TARGET_URLS_PATH + '.' if new_rows else 'Nothing to write.'}"
    )


if __name__ == "__main__":
    asyncio.run(discover())
