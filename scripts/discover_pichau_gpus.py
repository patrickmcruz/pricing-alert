"""Search-grid discovery for Pichau: crawls the store's search results for
RTX 5070 / RTX 5070 Ti and upserts any new matches into the `target_urls`
DB table (src/db/schema.py - see specs/target-urls-table/spec.md) - the same
manifest DiscoveryEngine already treats as the source of truth for tracked
SKUs.

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
from src.core.contract import TargetUrlEntry
from src.core.parsing_utils import has_maintenance_marker_in_html
from src.db.schema import initialize_schema as initialize_db_schema
from src.repositories.postgres_target_url_repository import PostgresTargetUrlRepository
from src.scrapers.pichau import extract_pichau_products

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


async def discover() -> None:
    await initialize_db_schema(settings.db_dsn)
    target_url_repo = PostgresTargetUrlRepository(dsn=settings.db_dsn)

    factory = BrowserFactory()
    existing = await target_url_repo.list_all()
    existing_urls = {entry.product_url for entry in existing}

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
            "target_urls - re-run this script once the site is back."
        )
        return

    new_entries = []
    seen_this_run = set()
    for row in all_found:
        if row["product_url"] in existing_urls or row["product_url"] in seen_this_run:
            continue
        seen_this_run.add(row["product_url"])
        new_entries.append(TargetUrlEntry(
            store_name=row["store_name"],
            search_keyword=row["search_keyword"],
            product_url=row["product_url"],
            brand=row["brand"],
            model=row["model"],
            product_title=row["product_title"],
        ))

    inserted = await target_url_repo.upsert_many(new_entries) if new_entries else 0

    print(
        f"\nDone. {len(all_found)} candidate(s) found, {inserted} new, "
        f"{len(all_found) - inserted} already tracked. "
        f"{'Wrote ' + str(inserted) + ' row(s) to target_urls.' if inserted else 'Nothing to write.'}"
    )


if __name__ == "__main__":
    asyncio.run(discover())
