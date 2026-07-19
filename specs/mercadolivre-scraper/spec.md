# Mercado Livre Scraper Spec

Documentation-only spec, written retroactively per the project's spec-driven design convention (`specs/README.md`) — `MercadoLivreScraper` (`src/scrapers/mercadolivre.py`) already exists, is registered, and is enabled in production; this captures the *why* behind its design so it doesn't have to be re-derived from the code.

## 1. What & Why

Track price/availability for SKUs on `mercadolivre.com.br` via the **official Mercado Livre API**, not HTML scraping — the one store in this project where a real, credentialed public API was available and used instead of a browser.

## 2. Design: the one store with no CSS-selector layer at all (until Pichau)

- **`transport_type = "http"`** — `PriceEngine` injects an `httpx.AsyncClient` (`HTTPClientFactory`) instead of a Playwright `Page`; no browser, no WAF to get past, because this is a first-party REST API, not a scraped page. `specs/pichau-scraper/spec.md` §4 later established this same "no `data/selectors/{store}.toml`, JSON in" pattern as a repeatable exception for API-driven/JS-embedded-data stores, but Mercado Livre is where it originated in this codebase.
- **OAuth client-credentials flow, cached in-memory**: `_get_access_token()` exchanges `ml_app_id`/`ml_secret_key` (`src/core/config.py`) for a bearer token via `/oauth/token`, caches it on the scraper instance with a 5-minute-early expiry buffer, and only re-authenticates once it's actually stale — avoids a token round-trip on every single SKU fetch.
- **Two distinct product shapes, because Mercado Livre itself has two**: a URL matching `/p/MLB\d+` is a **catalog product** (many sellers compete for one listing; the real "price" is the lowest current offer, fetched via `/products/{id}` + `/products/{id}/items`), otherwise it's a **direct item listing** (`/items/{id}`, one seller, one price). `fetch()` tags its returned JSON with `"type": "catalog"` or `"type": "item"` so `parse()` can dispatch to `_parse_catalog()`/`_parse_item()` without re-deriving which shape it's looking at.
- **`gold_pro` vs. plain listings map onto `price_cash`/`price_installments`**, the same "cash vs. installment-total" contract shape every other scraper follows: for catalog products, `price_cash` is the lowest offer across *all* listing types, `price_installments` is the lowest offer specifically among `gold_pro` listings (Mercado Livre's interest-free-installment tier) — if none exist, `price_installments` falls back to `price_cash`. `installment_count` is hardcoded to `10` when a `gold_pro` listing exists (documented in the code as "ML's universal standard for electronics," not something the API response spells out directly) and `1` otherwise.

## 3. Test coverage

`tests/unit/test_mercadolivre_fetch.py` covers the OAuth flow (token caching/refresh, credential-missing failure) and ASIN-equivalent ID extraction from both URL shapes. `tests/unit/test_mercadolivre_parser.py` covers `_parse_catalog`/`_parse_item` against fixture JSON for both product shapes, including the no-offers/unavailable path (`build_unavailable_contract`).

## 4. Non-goals

Not extending this store to the SP-API-style dormant/active split Amazon has (`specs/amazon-scraper/spec.md` §2) — there's no HTML-scraping fallback for Mercado Livre in this codebase; if the API credentials or app access ever become unavailable, this store simply stops being trackable rather than falling back to a scraper, since no such fallback was ever built.
