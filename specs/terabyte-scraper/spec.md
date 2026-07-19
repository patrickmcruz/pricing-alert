# Terabyte Scraper Spec

Documentation-only spec, written retroactively per the project's spec-driven design convention (`specs/README.md`) — `TerabyteScraper` (`src/scrapers/terabyte.py`) already exists, is registered, and is enabled in production; this captures the *why* behind its design so it doesn't have to be re-derived from the code.

## 1. What & Why

Track price/availability for every SKU discovered against `terabyteshop.com.br` (76 rows in `target_urls` as of `specs/target-urls-table/spec.md`'s migration — the largest single-store manifest in this project), on the standard per-product-page cron schedule.

## 2. Design

Same canonical `BaseScraper` shape as Kabum (`.agents/AGENTS.md` §5): Playwright transport, CSS selectors versioned in `data/selectors/terabyte.toml` (currently just `[v1]` — no selector-drift history yet, unlike Kabum's `v1`/`v2`).

Two deliberate deviations from the Kabum baseline, both load-bearing:

- **`wait_until="domcontentloaded"`, not `"networkidle"`**, and a store-specific, longer timeout: `settings.terabyte_navigation_timeout_ms` (45s, vs. the 30s `navigation_timeout_ms` default every other Playwright scraper uses) — Terabyte's product pages were observed loading slowly enough that the shared default timeout wasn't reliable; rather than raise the global default (which would slow down every store's timeout budget for a problem only this one has), it got its own config key.
- **`simulate_human_interaction()` after every navigation** (`src/core/utils.py`) — mouse movement, scrolling, hovering, and a Cloudflare-iframe interaction attempt, the same anti-bot evasion Amazon's scraper uses. Terabyte is gated behind bot detection the way Kabum's page isn't; this is what gets past it.
- **Availability and price are handled together, not price-first**: unlike Kabum (which returns `None` immediately on missing/zero price), Terabyte's `parse()` checks `is_available` *before* deciding whether a missing price is a real failure — `(price_cash is None or price_cash <= 0) and is_available` is what actually returns `None`. An out-of-stock Terabyte listing legitimately has no price element at all, so treating "no price" as always fatal would have misreported every sold-out SKU as a parse failure (`SelectorOutdatedException`-worthy) instead of a normal unavailable listing (`price_cash=Decimal("0.00")`, `is_available=False`).

## 3. Test coverage

`tests/unit/test_parsers.py::test_terabyte_product_parser` covers `parse()` against a fixture matching `v1`'s selectors, including the out-of-stock-with-no-price-element case described above. No dedicated `fetch()` test, same reasoning as Kabum.

## 4. Non-goals

Not adding the `StoreUnavailableException`/`has_maintenance_marker_in_html` mechanism Pichau introduced (`specs/pichau-scraper/spec.md` §4) — Terabyte hasn't been observed serving a maintenance/decoy page distinguishable from real selector drift. Worth adopting if it ever does.
