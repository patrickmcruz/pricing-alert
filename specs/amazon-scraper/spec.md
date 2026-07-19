# Amazon Scraper Spec

Documentation-only spec, written retroactively per the project's spec-driven design convention (`specs/README.md`) — `AmazonScraper` (`src/scrapers/amazon.py`) already exists, is registered, and is enabled in production; this captures the *why* behind its design, including a dormant sibling implementation, so it doesn't have to be re-derived from the code.

## 1. What & Why

Track price/availability for every SKU discovered against `amazon.com.br`, on the standard per-product-page cron schedule.

## 2. Architecture decision: HTML scraping is active, SP-API is dormant

Two implementations exist for this store:

- **`AmazonScraper`** (`@register_scraper`, active): direct Playwright/HTML scraping, same shape as Kabum/Terabyte — `fetch()` navigates and calls `simulate_human_interaction()` (Amazon gates behind bot detection), `parse()` reads `data/selectors/amazon.toml` and extracts price/title/availability/installments from the DOM.
- **`AmazonSPAPIScraper`** (`src/scrapers/amazon_spapi.py`, **not** `@register_scraper` — plays no part in orchestration): a Selling Partner API client using Product Pricing API v0's `getItemOffers`, `transport_type = "http"` (no browser). This would be the "official," ToS-compliant route, and the code is complete and tested (`tests/unit/test_amazon_spapi_fetch.py`, `test_amazon_spapi_parser.py`) — but reaching *real* (non-sandbox) prices requires a production `refresh_token` obtained via self-authorization in Seller Central, which in turn requires an active Amazon seller account. This project doesn't have one, so the class can currently only reach the SP-API **sandbox**, which returns static mock data for a fixed set of test ASINs, not real prices for arbitrary tracked SKUs.

**Decision:** ship the HTML scraper as the active path now; keep `AmazonSPAPIScraper` in the codebase, fully wired and tested, so switching over is a one-line change (flip `@register_scraper` onto it, unregister the HTML version) *if* production seller access is obtained later — not a rewrite. `scripts/discover_amazon_catalog.py` already uses this same class's Catalog Items API (a different SP-API endpoint, with looser access requirements) to search for ASINs, so the dormant client isn't unused code — it has one live caller today, just not for pricing.

## 3. HTML scraper (`AmazonScraper`) design notes

- **`wait_until="domcontentloaded"` + `simulate_human_interaction()`** (`src/core/utils.py`) — same anti-bot evasion pattern as Terabyte; Amazon's product pages are behind bot detection strong enough that a bare `page.goto` isn't reliable.
- **Installment parsing is regex-based, not selector-based, for the *value***: the installment element's text (e.g. `"Em até 12x R$ 399,99 sem juros"`) is still located via a `data/selectors/amazon.toml` CSS selector, but its *content* is extracted with `_INSTALLMENT_RE` rather than a second selector, because Amazon renders the count and the per-installment price as sibling text nodes inside one element, not two separately selectable ones the way Kabum/Terabyte do.
- **Selectors are long, generated-looking CSS paths** (`#corePriceDisplay_desktop_feature_div > div > div.a-section...`) — Amazon's own markup is deeply nested and class names are framework-generated (`a-price`, `aok-align-center`), unlike Kabum/Terabyte's short hand-authored classes. This makes the selector more brittle to Amazon's own frontend changes than the other stores'; if `SelectorOutdatedException` starts firing frequently for this store, that brittleness — not a code bug — is the likely cause.

## 4. Test coverage

`tests/unit/test_parsers.py::test_amazon_product_parser` covers `AmazonScraper.parse()` (fixture-based). `tests/unit/test_amazon_spapi_fetch.py` and `test_amazon_spapi_parser.py` cover the dormant `AmazonSPAPIScraper` end-to-end (token exchange, ASIN extraction, offer-JSON parsing) despite it not being live — so if it's ever promoted to `@register_scraper`, its correctness is already verified, not assumed.

## 5. Non-goals

Not attempting production SP-API access as part of this spec — that requires an actual Seller Central account, an external/business dependency, not a code change.
