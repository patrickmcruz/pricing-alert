# System Spec

Supersedes `.gemini/.artifacts/artifact1-system_spec.md` (historical — described a SQLite, single-database, GPU-only version of this app; kept for archaeology, not accuracy).

## 1. Overview

A local-first, single-user, 100% open-source price monitoring application. Originally scoped to GeForce RTX 5070 / RTX 5070 Ti, but the catalog (`categories`/`brands`/`products`, see [`data-contract/spec.md`](../data-contract/spec.md)) is deliberately generalized — any product category can be tracked, not just GPUs, without a schema change.

The system runs scheduled scraping jobs against multiple Brazilian e-commerce stores, normalizes what it extracts into a common contract, persists full price history, evaluates user-defined alert rules against every new observation, and exposes a Streamlit dashboard for configuration and analysis.

## 2. Technology Stack

| Component | Technology | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| Database | PostgreSQL (via `asyncpg`) | Not SQLite — migrated mid-project (see §7, "What changed since the original artifact") |
| Data Validation | Pydantic v2 | `frozen=True, extra="forbid"` on every contract |
| Scheduler | APScheduler (`AsyncIOScheduler`) | |
| HTTP Client | HTTPX (HTTP/2) | For stores with a usable REST API (Mercado Livre) |
| Browser Automation | Playwright (async) + `playwright-stealth` | For stores requiring rendered-DOM scraping (Kabum, Terabyte) |
| Dashboard | Streamlit | `src/ui/` |
| Containerization | Docker Compose | 3 services: `db`, `orchestrator`, `dashboard` |

## 3. Environments

Four `APP_ENV` values (`develop`/`staging`/`production`/`test`), each resolving to its **own** PostgreSQL database on the same server (`pricing_dev`/`pricing_staging`/`pricing`/`pricing_test` — see `config.toml`). This is deliberate: local iteration (trimmed listing set, fast scrapes) and production (full catalog, real schedule) can never cross-contaminate, because they're not just different config — they're physically different databases.

The Docker orchestrator container is *always* `APP_ENV=production`; it re-asserts the full `data/target_urls.json` catalog as active on every boot (idempotent upsert via `DiscoveryEngine.run_discovery`), so production self-heals from any accidental deactivation. Local dev/test work never touches this path.

## 4. Extraction Strategy

Two extraction engines behind a `ClientFactory` protocol (`BaseScraper.transport_type` selects which one `PriceEngine` injects):

- **`"http"`** — `httpx.AsyncClient` for stores with a usable REST/JSON API (Mercado Livre's official API).
- **`"browser"`** — Playwright `Page` (via `BrowserFactory`, stealth-hardened) for stores that only render via JS or actively block plain HTTP (Kabum, Terabyte).

Every concrete scraper self-registers via `@register_scraper` (`src/core/registry.py`) when `src/scrapers/__init__.py` auto-imports the package — no orchestration file needs editing to add a store. A store `enabled: true` in `data/target-stores-list.json` with no matching registered scraper is a **hard startup failure** (`MissingScraperError`), not a silent skip.

## 5. Discovery Strategy

Two coexisting discovery models, deliberately kept separate rather than unified into one framework:

1. **Static manifest** (`data/target_urls.json`, loaded by `DiscoveryEngine`) — the default for every store so far. A human curates a fixed list of product URLs; `DiscoveryEngine` resolves each into the catalog and upserts a `listings` row. Simple, zero anti-bot surface beyond the product page itself, but doesn't discover *new* products on its own.
2. **Search-grid spider** — crawls a store's search results page for a query, extracts candidate product URLs/titles automatically. Higher anti-bot risk (search pages are a common bot-detection trigger) and requires grid-parsing logic a single-product scraper doesn't need. An earlier generic attempt at this (`src/spiders/`) was removed — it never reached a working state and added a parallel class hierarchy without delivering functionality (see `.agents/AGENTS.md` §5). It is **not** gone as a concept — `pichau-scraper` (see `specs/pichau-scraper/`) is the first store to reintroduce it, scoped to exactly one store rather than a speculative generic framework, per the guidance that already existed for this decision.

## 6. Architecture Principles (unchanged from the original artifact)

- Strategy Pattern for scraper implementations; Repository Pattern per persistence entity.
- Strict separation: `fetch()` (network I/O only) vs. `parse()` (pure, deterministic, no I/O) on every `BaseScraper`.
- Selectors are never hardcoded in Python — externalized to `data/selectors/{store}.toml`, versioned (`[v1]`, `[v2]`...) so a UI change bumps a TOML block, not application code.
- Every layer (extraction, orchestration, persistence, alerting, presentation) is independently unit-testable without live network, browser, or database access — except the repository layer, which intentionally tests against a real `pricing_test` Postgres instance (see `TESTING.md`) rather than mocking SQL.

## 7. What changed since the original artifact

- **Persistence**: SQLite (`db_path`, one file) → PostgreSQL (`db_dsn`, one database per environment). See `README.md`'s "Database Schema" section for the current table list.
- **Catalog**: GPU-specific fields folded into `categories`/`brands`/`products` with category-specific attributes (chipset, VRAM...) in `products.specs` (JSONB) — the schema no longer assumes every tracked item is a GPU.
- **Schema identifiers**: originally Portuguese (`loja`, `produto`, `anuncio`) mixed with English columns; fully renamed to English — see `git log -- src/db/schema.py` for the rename commit. Translation lives only in `pt-BR`/`en-US` UI copy (`src/core/i18n.py`), never the schema.
- **Alerting domain** (`src/alerts/`) added — not in the original artifact at all.
- **Store registry / transport abstraction** (`@register_scraper`, `ClientFactory`) added, replacing hand-wired scraper instantiation in `main.py`.
