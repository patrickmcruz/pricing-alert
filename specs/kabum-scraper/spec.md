# Kabum Scraper Spec

Documentation-only spec, written retroactively per the project's spec-driven design convention (`specs/README.md`) — `KabumScraper` (`src/scrapers/kabum.py`) already exists, is registered, and is enabled in production; this captures the *why* behind its design so it doesn't have to be re-derived from the code.

## 1. What & Why

Track price/availability for every SKU discovered against `kabum.com.br` (`data/target_urls.json`'s successor, the `target_urls` DB table — see `specs/target-urls-table/spec.md`), on the standard per-product-page cron schedule every other enabled store uses.

## 2. Design

Follows the canonical `BaseScraper` shape (`.agents/AGENTS.md` §5) exactly: HTML scraping via Playwright (default `transport_type = "browser"`), `fetch()` does network I/O only (`page.goto` + `page.content()`), `parse()` is pure/deterministic and reads CSS selectors from `data/selectors/kabum.toml`.

- **Two selector versions coexist** (`[v1]`, `[v2]` in `kabum.toml`) — `parse()` is pinned to `v2` (`h4.text-4xl` for price, a nested `span`/`b` structure for installments). `v1`'s survival in the file isn't dead config: `parser_version` is recorded on every `PriceContract` specifically so a selector-drift incident can be traced to which version was live at the time (`specs/data-contract/spec.md` §1) — keeping `v1` around is a paper trail of the site's last redesign, not an active fallback path (there's no runtime logic that tries `v1` if `v2` fails; only `load_selectors("v2")` is called).
- **Installment handling has a repair step other scrapers don't need**: Kabum's installment-count element (`span.block.my-12`) sometimes yields just the per-installment value rather than the total, so `parse()` multiplies `price_installments * installment_count` when the parsed value is smaller than `price_cash` — a defensive correction for a specific markup quirk on this store, not a general contract expectation.
- **No anti-bot handling** (no `simulate_human_interaction`, unlike Amazon/Terabyte) and no `has_maintenance_marker_in_html` check (the mechanism Pichau introduced, `specs/pichau-scraper/spec.md` §4) — Kabum hasn't been observed hitting either failure mode. Worth adding if it ever does; not retrofitted speculatively.

## 3. Test coverage

`tests/unit/test_parsers.py::test_kabum_product_parser` covers `parse()` against a hand-written fixture matching the `v2` selectors. No dedicated `fetch()` test — same as Terabyte/Amazon, `fetch()` is a thin Playwright wrapper not considered worth mocking in isolation.

## 4. Non-goals

Not migrating to a JSON-embedded-data parsing approach like Pichau (`specs/pichau-scraper/spec.md` §4) — Kabum's markup is real, stable, server-rendered DOM with no evidence of the Next.js/RSC pattern that made CSS selectors unworkable for Pichau. CSS selectors remain the right tool here.
