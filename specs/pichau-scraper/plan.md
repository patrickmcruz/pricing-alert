# Pichau Scraper + Discovery Plan

Implements `spec.md`. Two independent pieces: a one-off/manual discovery script, and a standard registered scraper for ongoing monitoring. Both fetch via Playwright (Cloudflare blocks plain HTTP clients — see spec §4) but parse via embedded-JSON extraction, not CSS selectors — the one part of the original DOM-scraping plan that turned out wrong.

## Files

| File | Purpose |
|---|---|
| `src/scrapers/pichau.py` | `PichauScraper(BaseScraper)`, `@register_scraper`, default `transport_type="browser"` (Playwright, same as Kabum/Terabyte — see spec §4). Also hosts `extract_pichau_products()`, the shared RSC-JSON extraction primitive. |
| `scripts/discover_pichau_gpus.py` | Fetches the two search URLs via `BrowserFactory`, extracts candidate products via `extract_pichau_products()`, upserts into `data/target_urls.json`. Not wired into `DiscoveryEngine` or orchestrator boot — run manually. |
| `tests/unit/test_pichau_parser.py` | Parser tests against synthetic fixtures that reproduce the real `self.__next_f.push(...)` RSC-JSON shape (verified against live-fetched real HTML during this revision — see spec §4). |
| `tests/unit/test_discover_pichau_gpus.py` | Tests the search-results extraction logic against the same kind of fixture. |

`data/target-stores-list.json`'s existing `"pichau"` entry stays `"enabled": false` until the discovery script has actually been run against the live site and its output reviewed (spec §4) — already done once during this revision (see Verification below); flip it once that output has been reviewed and accepted.

## `extract_pichau_products()` design (`src/scrapers/pichau.py`)

Both the scraper and the discovery script need the same thing: every product object embedded in a Pichau page's HTML, regardless of how that HTML was fetched. This function is that shared primitive:

1. `_PUSH_ARG_RE` finds each `self.__next_f.push([id, "..."])` call and captures its `[id, "..."]` argument.
2. `json.loads(...)` on that captured argument (it's valid JSON on its own: an int and a string) un-escapes the inner string into real JSON syntax — this is the key step that turns `\"id\":62393` (as it appears raw in the HTML, escaped for embedding in a JS string literal) into a genuine `"id":62393` byte sequence.
3. `_PRODUCT_ANCHOR_RE` (`{"id":<n>,"sku":"`) finds where each product object starts in that un-escaped text; `json.JSONDecoder.raw_decode` reads exactly one balanced JSON value from that position, so it doesn't matter what wraps it (arrays, other RSC nodes, `$ref`-style placeholders elsewhere in the payload).
4. Objects lacking a `"pichau_prices"` key are dropped — these are incomplete cross-references (e.g. a "recently viewed" stub carrying only `id`/`sku`), not a fully described product.
5. Deduplicated by `sku` — the same product object is often repeated across multiple RSC chunks on one page (e.g. once in the grid, once in a recommendation widget).

Verified against real, Playwright-fetched HTML for both page types (36 correct RTX 5070 products recovered from the search page; the exact product recovered from its own product page) — not just hand-written fixtures.

## `discover_pichau_gpus.py` design

1. `BrowserFactory().create(scraper=None)` for a Playwright `Page` — `page.goto(url, wait_until="networkidle")` against each of the two search URLs, same navigation pattern `PichauScraper.fetch()` uses.
2. `parse_search_results(html, search_keyword)`: pure function. Calls `has_maintenance_marker_in_html()` first (same reasoning as `PichauScraper.parse()` — see spec §4's shared mechanism note), then `extract_pichau_products()`, then filters by chipset (`_matches_chipset`, reusing the alias-normalization approach `DiscoveryEngine._resolve_chipset_name` already uses, so "RTX 5070 Ti" and "5070ti" don't become two different `products` rows) and maps each hit into the manifest row shape. Brand comes straight from the embedded `marcas_info.name` — no title-guessing needed, unlike the original DOM-scraping plan.
3. Deduplicate against what's already in `data/target_urls.json` by `product_url` — this script is safe to re-run; it only adds new rows, never removes or duplicates existing ones (same idempotency contract `migrate_target_urls.py`/`save_skus` already follow elsewhere).
4. Write the merged manifest back to `data/target_urls.json`, matching the existing shape (`store_name`, `search_keyword`, `product_url`, `brand`, `model`, `product_title`).
5. Print a summary (found / new / already-tracked) — this is a manually-run tool; the operator needs to see what happened, same reasoning as `scripts/migrate_target_urls.py`'s own summary line.

## `PichauScraper` design

- `__init__`: `store_name="pichau"`, `base_url="https://www.pichau.com.br"`. No `transport_type` override — the `BaseScraper` default (`"browser"`) is correct here.
- `fetch()`: Playwright `page.goto(product_url, wait_until="networkidle", timeout=settings.navigation_timeout_ms)`, return `page.content()` — identical shape to `KabumScraper.fetch()`. No `simulate_human_interaction()` beyond what `BrowserFactory` already applies (stealth init script, randomized viewport) — that combination was sufficient to get past Cloudflare during verification; add more only if that changes.
- `parse()`: `has_maintenance_marker_in_html()` first (raises `StoreUnavailableException`, same mechanism as every other check in this initiative — see spec §4's "New shared mechanism" section), then `extract_pichau_products()`, then picks the object whose `url_key` matches the SKU's own URL (falling back to the first result — a product page should only ever embed one, but this makes the match explicit rather than assumed). Maps `pichau_prices.avista` → `price_cash`, `pichau_prices.base_price` → `price_installments`, `pichau_prices.max_installments` → `installment_count`, `stock_status == "IN_STOCK"` → `is_available`. Raises `SelectorOutdatedException` if no product JSON is found at all (the RSC payload shape itself has changed, not just a value inside it — that's the equivalent failure mode to a stale CSS selector for a store with no CSS selectors).

## Verification

1. `pytest tests/unit/test_pichau_parser.py tests/unit/test_discover_pichau_gpus.py -v` — confirms parsing logic against synthetic fixtures reproducing the real RSC-JSON shape.
2. Already done during this revision, outside of pytest: fetched the live search page and a live product page via a real Playwright/`BrowserFactory` session, ran both `parse_search_results()` and `PichauScraper.parse()` against that real HTML, and confirmed correct extraction (36 real, correctly-separated RTX 5070 and 36 RTX 5070 Ti products across the two search URLs, zero overlap between them; correct price/title/availability on the product page). Also confirmed a plain `httpx` GET gets Cloudflare's 403 decoy page instead — that's *why* the scraper stays on the Playwright transport. Re-run this kind of direct check if the RSC payload shape ever seems to have changed (e.g. `SelectorOutdatedException` starts firing in production).
3. Already done during this revision: ran `python scripts/discover_pichau_gpus.py` for real — it wrote 72 real rows (36 + 36, every one with a brand resolved from `marcas_info.name`) into `data/target_urls.json`. Review that diff before committing.
4. Only then: flip `"pichau": {"enabled": true}` in `data/target-stores-list.json`, and confirm `MissingScraperError` doesn't fire on the next orchestrator boot (it won't — `PichauScraper` self-registers via `@register_scraper` regardless of the flag; the flag only controls scheduling).
5. Run `scripts/run_all_scrapers.py` locally (`APP_ENV=develop`) against the newly-discovered URLs to confirm end-to-end price extraction before trusting it in production.
