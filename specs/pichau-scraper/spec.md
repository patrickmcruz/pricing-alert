# Pichau Scraper + Discovery Spec

## 1. What & Why

Track RTX 5070 and RTX 5070 Ti listings from `pichau.com.br`, sourced from two search-result pages instead of hand-curated product URLs:

- `https://www.pichau.com.br/search?q=5070&product_category=6459&rgpu=7725` (RTX 5070)
- `https://www.pichau.com.br/search?q=5070&product_category=6459&rgpu=7726` (RTX 5070 Ti)

`product_category=6459` scopes to Pichau's GPU category and `rgpu=<facet id>` is its exact GPU-model filter facet - narrower and more reliable than a plain free-text `?q=` search (which is what this spec started from before being refined to these filtered URLs).

This is deliberately the first store onboarded via **search-grid discovery** rather than the static-manifest pattern (`data/target_urls.json`, manually curated) every other store uses. `.agents/AGENTS.md` §5 already anticipated this: the original generic `src/spiders/` framework was removed because it never worked and added a parallel class hierarchy speculatively; it explicitly left the door open to "reintroduce [search-grid discovery] later as its own scoped initiative." This is that initiative, scoped to exactly one store.

## 2. Requirements

- Discover every RTX 5070 / RTX 5070 Ti product Pichau currently lists, from the two search URLs above.
- For each discovered product: resolve it into the catalog (`categories`/`brands`/`products`, see `specs/data-contract/spec.md`) and persist a `listings` row, same shape every other store's discovery produces — downstream code (scheduler, dashboard, alerts) must not need to know Pichau's listings arrived differently than Kabum's.
- Ongoing price monitoring after discovery uses the same `BaseScraper` contract as every other store (`fetch()`/`parse()` per product page) — discovery finds URLs once; the registered `PichauScraper` scrapes each one on its own cron schedule after that, same as Kabum/Terabyte/Mercado Livre.
- No CSS-selector layer: see §4 — the real markup isn't DOM-selectable, so this store extracts embedded JSON instead (same class of exception `.agents/AGENTS.md` §5 already carves out for API-driven stores like Mercado Livre).

## 3. Architecture decision: discovery script, not a live per-boot subsystem

Two ways to wire search-grid discovery in:

**(a) A standalone script** (`scripts/discover_pichau_gpus.py`) that crawls the two search URLs, extracts candidate products, and upserts them into `data/target_urls.json` — the same file `DiscoveryEngine`/`migrate_target_urls.py` already treat as the manifest of record. Run manually (or on a slow schedule, e.g. weekly) to pick up new Pichau listings; the existing static-manifest pipeline (`DiscoveryEngine.run_discovery`, called on every orchestrator boot) takes over from there for actual price monitoring, completely unaware discovery was automated for this one store.

**(b) A live component** wired directly into `DiscoveryEngine.run_discovery()`, crawling Pichau's search pages on every orchestrator boot alongside reading the static manifest.

**Decision: (a).** Reasons:
- Search-result pages are a materially higher anti-bot/rate-limit surface than product pages (this is exactly why the original `src/spiders/` attempt was flagged as higher-risk). Running that crawl on *every container boot* multiplies the exposure for no benefit — GPU listings don't appear and disappear fast enough to justify checking more than occasionally.
- It keeps `DiscoveryEngine` and the boot sequence completely unchanged. If the Pichau discovery script breaks (selector drift, site down — see §5), it fails in isolation, on its own run, not as a startup dependency of the entire orchestrator.
- It matches the existing manifest-of-record architecture exactly: from `DiscoveryEngine`'s perspective, Pichau's rows arrived in `target_urls.json` the same way every other store's did. No special-casing anywhere downstream.

If Pichau listings genuinely need same-day freshness later, promoting this to a scheduled job (cron, or a `trigger_requests`-style manual button) is a small, additive change — not a rewrite.

## 4. Resolved: site is up, and it isn't CSS-selector territory at all

`pichau.com.br` was returning its own "Site em Manutenção" maintenance page for **every** URL during this spec's initial authoring — confirmed via a live Playwright fetch, not a bot-block (no Cloudflare/challenge markers; a genuinely styled maintenance page with Pichau's own branding). That made the original plan (Magento DOM selectors, informed only by `/skin/frontend/pichau/default/...` asset paths, a Magento 1.x convention) unverifiable, so it shipped as placeholders.

The site is back up as of this spec's revision. A direct `curl` fetch (no browser, no JS execution) against both search URLs and a real product page returned `200` with full real content, no maintenance page, no bot challenge — which revealed the original plan was wrong about the parsing layer, though (see below) not about the transport:

1. **The frontend is a Next.js storefront, not classic Magento DOM.** Magento is still the backend (GraphQL, judging by field shapes like `pichau_prices`/`marcas_info`), but the rendered page has no stable per-product CSS classes to select — product data isn't in scrapeable DOM elements at all.
2. **The real product data is embedded as JSON, in the HTML.** Every page (product page *and* search-results page) ships the full GraphQL product object(s) inside `self.__next_f.push([id, "..."])` calls — Next.js's React Server Component streaming format. A product page embeds exactly one product's object; a search-results page embeds one per listed product (36 were found for the live `rtx 5070` search at authoring time).

Consequently, this store has **no `data/selectors/pichau.toml` and no CSS-selector layer at all** — the same architectural exception `MercadoLivreScraper` already established for API-driven stores (see `.agents/AGENTS.md` §5, "one `data/selectors/<store>.toml` **if HTML-based**"). `src/scrapers/pichau.py::extract_pichau_products()` is the shared extraction primitive (imported by both `PichauScraper.parse()` and `scripts/discover_pichau_gpus.py`): it un-escapes each `push()` argument's JSON-encoded string, then locates each embedded product object by anchoring on `{"id":<n>,"sku":"` and reading it with `json.JSONDecoder.raw_decode` — which parses exactly one balanced JSON value from that position regardless of what wraps it, so it doesn't need to know the surrounding RSC structure.

**Transport still has to be Playwright, though** — this is the one place the original plan was right. A plain `httpx` GET (identical UA/Accept headers to the successful `curl`) got a `403` from Cloudflare, which serves a decoy page styled exactly like a real "Site em Manutenção" maintenance page — the very same title text this store's maintenance detection was originally built around, meaning what looked like the site being down during initial onboarding may actually have been this same bot-block all along, not a genuine outage. A real Chromium session via `BrowserFactory`, by contrast, got the genuine page every time. So `transport_type` stays the `BaseScraper` default (`"browser"`); only the *parsing* mechanism changed from CSS selectors to JSON extraction. Verified against real, live-fetched HTML for both page types and both transports during this revision — 36 correct RTX 5070 products recovered via Playwright on the search page (confirmed with zero overlap against the 36 RTX 5070 Ti results from the other search URL), and the exact product recovered from its own product page — not just against hand-written fixtures. `scripts/discover_pichau_gpus.py` was also run for real, writing 72 real rows (36 + 36) into `data/target_urls.json`, every one with a brand resolved.

Price semantics, read from `pichau_prices` (present on every embedded product object): `avista` (PIX/cash-discounted price) maps to `price_cash`; `base_price` (full price, what installments are computed from) maps to `price_installments`; `max_installments` maps to `installment_count` — the same "cash vs. installment-total" shape `compute_discount()` already expects from every other scraper. `stock_status == "IN_STOCK"` maps to `is_available`.

**`"pichau"` stays `"enabled": false` in `data/target-stores-list.json` until `scripts/discover_pichau_gpus.py` has actually been run against the live site and its output reviewed** — flip it to `true` only after that (this is now unblocked; nothing about the site itself is preventing it anymore).

### New shared mechanism: `StoreUnavailableException`

This blocker surfaced a real gap: a maintenance page and a page whose parsing has genuinely broken (selector drift for a DOM-based store, an RSC-shape change for this one) look identical from inside `parse()` — both fail to find what they're looking for, so both would previously raise `SelectorOutdatedException`. That's a false alarm for a maintenance page (nothing to fix, just retry later) and a real one for drift (go fix the parsing) — conflating them means every store outage risks getting "fixed" by someone chasing something that was never actually broken.

Added as a general capability, not Pichau-specific, since any store can hit this:

- `StoreUnavailableException` (`src/core/base_scraper.py`) — distinct from `SelectorOutdatedException`.
- `has_maintenance_marker()` (`src/core/parsing_utils.py`) — checks a `BeautifulSoup` document's `<title>` against known "store is down" phrases (PT + EN), same shape as the existing `has_out_of_stock_marker()`. `has_maintenance_marker_in_html()` is the same check directly against a raw HTML string (via a `<title>` regex) for scrapers like this one that don't otherwise build a `BeautifulSoup` tree. Title-only by design: body text risks false positives (e.g. a review mentioning "manutenção").
- `SkuRunStatus.STORE_UNAVAILABLE` (`src/core/execution.py`) + a dedicated `except` branch in `PriceEngine.run_scraper` (`src/engine/scheduler.py`), logged as `warning` rather than `critical`/`error` — an outage is an expected-to-recur external condition, not a code problem.
- `PichauScraper.parse()` and `discover_pichau_gpus.parse_search_results()` both call `has_maintenance_marker_in_html()` first, before any real extraction — the reference implementation for any other scraper that wants the same protection.

Not retrofitted into the existing Kabum/Terabyte/Mercado Livre/Amazon scrapers in this change — each would need its own real maintenance-page marker text confirmed, which none of them have hit yet. Adopting the same one-line check in `parse()` is the pattern to follow if/when one of them does.

## 5. Non-goals

- Not building a generic multi-store spider framework — this is Pichau-specific code, matching the actual product pages/scrapers pattern (each store gets its own file, no shared spider base class speculatively built for stores that don't need it yet).
- Not adding pagination handling, infinite scroll, or filtering beyond what the two given search URLs already return — if Pichau's result set for these queries turns out to be paginated, that's a follow-up once the site is reachable and real behavior can be observed.
