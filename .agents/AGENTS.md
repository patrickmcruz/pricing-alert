# Agent Context & Blueprint: GPU Price Tracker (Test-Driven Architecture)

You are a Senior Full-Stack Software Architect and Data Engineer. Your objective is to build and maintain a modular, single-user, 100% open-source web application for automated GPU price monitoring (specifically GeForce RTX 5070 and RTX 5070 Ti) across Brazilian e-commerce stores.

## 1. Architectural Philosophy & Constraints
* **Test-Driven & Deterministic:** The system must be designed for maximum testability. Business logic, parsing, and orchestration must be independently testable without network access, browser automation, or a live database.
* **Separation of Concerns:** Network I/O, HTML parsing, orchestration, and persistence are strictly decoupled.
* **Dependency Injection & IoC:** Never instantiate HTTP clients, Playwright contexts, or databases inside the scrapers or the scheduler. Use factories and inject them.
* **No External Dependencies:** The app runs entirely locally. No paid APIs.
* **Configuration & Gitflow Environments:** All configurations MUST be centralized in a root `config.toml` file. The application relies on `APP_ENV` (develop, staging, production) to load environment-specific variables natively via `tomllib` (in `src/core/config.py`).

## 2. Mandatory Technology Stack
* **Language:** Python 3.11+
* **Dependencies & Tooling:** All dependencies, test configurations (`pytest`), and static typing rules (`mypy`) MUST be centrally managed in `pyproject.toml`. Do not create `requirements.txt` or `pytest.ini`.
* **Orchestrator:** APScheduler (`AsyncIOScheduler`)
* **Database:** PostgreSQL (via `asyncpg`, Repository Pattern) - see `config.toml`'s per-`APP_ENV` `db_host`/`db_name` blocks and "Database Schema" in `README.md`
* **Extraction:** HTTPX (HTTP/2 enabled) and Playwright (async) + `playwright-stealth`.
* **Data Validation:** Pydantic v2.
* **Interface:** Streamlit.
* **QA & Testing:** Pytest, `pytest-asyncio`, `pytest-mock`, `respx`, `mypy`, `ruff`, `black`.

## 3. Strict Directory Governance
**CRITICAL:** All shared abstractions, contracts, configurations, and reusable utilities MUST reside exclusively within `src/core`. Do not duplicate shared logic across scraper implementations.

```plaintext
/gpu-price-tracker
├── /src
│   ├── /core                         # Shared architecture and abstractions
│   │   ├── __init__.py
│   │   ├── contract.py               # Pydantic data models (PriceContract, ProductSKU)
│   │   ├── base_scraper.py           # Abstract Base Class for Scrapers
│   │   ├── config.py                 # Application configuration via tomllib
│   │   ├── browser.py                # Playwright factory
│   │   ├── http_client.py            # HTTPX client factory
│   │   ├── parsing_utils.py          # Shared parsing helpers (price cleaning, discount, stock)
│   │   ├── contract_factory.py       # Shared PriceContract construction helpers
│   │   ├── registry.py               # @register_scraper self-registration for scraper classes
│   │   ├── transport.py              # ClientFactory Protocol shared by BrowserFactory/HTTPClientFactory
│   │   └── utils.py                  # Shared helper functions (jitter, anti-bot simulation)
│   ├── /scrapers                    # Scraper Engine (parses specific Product Pages); self-registers via @register_scraper
│   ├── /engine                       # Orchestration (scheduler.py, discovery.py)
│   ├── /db
│   │   └── schema.py                 # Single source of truth for the PostgreSQL schema + connect() (asyncpg, FKs enforced natively)
│   ├── /repositories                 # Persistence layer (PostgreSQL/asyncpg implementation, Repository Pattern per entity)
│   ├── /alerts                       # Alerting domain: rules, evaluation, notification delivery
│   │   ├── contracts.py              # AlertRule, AlertEvent (Pydantic v2)
│   │   ├── evaluator.py              # Pure AlertEvaluator (no I/O, fixture-testable)
│   │   ├── repository.py             # AlertRepository ABC + postgres_alert_repository.py
│   │   ├── dispatcher.py             # AlertDispatcher - wired into PriceEngine via on_price_saved
│   │   └── channels/                 # Pluggable NotificationChannel implementations (e.g. telegram.py)
│   ├── /ui                           # Streamlit application
│   └── /data
│       └── target-stores-list.json   # Store definitions (Cron configs, enabled flag)
├── /data/selectors                   # TOML config files for externalized CSS selectors
├── /tests
│   ├── /fixtures                     # Static HTML for parser tests
│   ├── /unit
│   ├── /integration
│   ├── /e2e
│   └── /smoke
```

## 4. Data Contracts (Pydantic V2)

All extracted data must be normalized into the `PriceContract` model before leaving the scraper.

* Models must use `ConfigDict(frozen=True, extra="forbid", validate_assignment=True)`.
* Use `UUID` for `execution_id` to ensure end-to-end traceability.
* Use `Decimal` (not float) for all monetary fields (`price_cash`, `price_installments`).
* Extract both Cash (À vista) and Installment (Parcelado) prices, as well as the maximum `installment_count` (e.g. `10`).
* Timestamps must use timezone-aware UTC (`datetime.now(timezone.utc)`).

## 5. Scraper Architecture & Pluggable Registry

Discovery of new SKUs is handled by `DiscoveryEngine` (`src/engine/discovery.py`) reading a static manifest (`data/target_urls.json`) and persisting `ProductSKU` records into the `listings` table. `main.py` also calls this on every orchestrator boot (`APP_ENV=production` only) so production's SKU set self-heals via the idempotent upsert in `save_skus()`, independent of whatever a local `pricing_dev` session has trimmed. **The earlier "two-tier spider/scraper" design (live search-grid crawling via `src/spiders/`) was deprecated and removed**: it never reached a working state (`DiscoveryEngine` never invoked it, and its network-fetch half was an unimplemented stub), so it added coupling and duplicated logic without delivering functionality. Live search-grid discovery may be reintroduced later as its own scoped initiative — it is a materially different problem (higher anti-bot risk, grid parsing) from single-product-page scraping and should not be rebuilt as a parallel class hierarchy without a clear need.

**Scraper Engine (Scrapers):** Concrete scrapers inherit from `BaseScraper` and visit the exact product URLs discovered by the Discovery Engine.

Every concrete scraper class **must** be decorated with `@register_scraper` (`src/core/registry.py`) so it self-registers by `store_name` when `src/scrapers/__init__.py` auto-imports the package — this is what lets `main.py` wire up scrapers via `get_registered_scrapers()` without per-store edits. Adding a new store means: one new `src/scrapers/<store>.py` (decorated, using the shared helpers in `src/core/parsing_utils.py`/`contract_factory.py`), one `data/selectors/<store>.toml` if HTML-based, and `"enabled": true` for that store in `data/target-stores-list.json`. No other file should need changes. If a store is marked `enabled: true` in that manifest but has no matching registered scraper, `PriceEngine.build_schedule()` raises `MissingScraperError` at startup rather than silently skipping it.

Concrete scrapers must implement strictly separated methods:
1. **`fetch(self, sku: ProductSKU, client: Any) -> str`**: Performs ONLY network I/O. Returns raw HTML. 
2. **`parse(self, document: str, sku: ProductSKU) -> Optional[PriceContract]`**: Performs ONLY data extraction using CSS selectors loaded from the `data/selectors/{store}.toml` file. **Must be 100% deterministic and unit-testable**.
3. **`execute()`**: Orchestrates the fetch and parse pipeline.

**Resilience, Fallbacks & Versioning:** 
Scrapers MUST NOT hardcode CSS classes, IDs, or XPath expressions under any circumstances. If a dynamic or primary selector fails, any fallback selectors MUST also be read dynamically from the corresponding `data/selectors/{store}.toml` file. If a `parse()` method cannot find critical DOM elements using its TOML selectors, it must raise a `SelectorOutdatedException`. The `PriceContract` records the `parser_version` to maintain data lineage.

## 6. Orchestration & Persistence

* **Scheduler (`PriceEngine`):** Responsible for loading `ProductSKU` records from the repository and coordinating execution of the Scrapers. Catches `SelectorOutdatedException` gracefully to prevent batch crashes. Also selects the correct `ClientFactory` per scraper via `BaseScraper.transport_type` (`"browser"` for Playwright HTML scrapers, `"http"` for JSON/REST scrapers like Mercado Livre) - `PriceEngine` is constructed with a `client_factories: dict[str, ClientFactory]`, never a single factory.
* **Repository Pattern:** Database operations are isolated behind one interface per entity (`PriceRepository`, `CatalogRepository`, `StoreRepository`, `ExecutionRepository`, `TriggerRepository`, `AlertRepository`). Scrapers never talk to Postgres directly.
* **Schema (`src/db/schema.py`):** Single source of truth for every `CREATE TABLE`/index, plus a `connect(dsn)` helper (asyncpg, jsonb codec registered) - repositories no longer each own their own `initialize_schema()`. Call `initialize_schema(dsn)` once at boot (or from a script/Streamlit page) instead of per-repository. Core tables: `stores`, `categories`/`brands`/`products` (normalized catalog - category-specific attributes like `chipset` live in `products.specs` JSONB rather than dedicated columns), `listings` (tracked SKUs, soft-deleted via `is_active` rather than hard-deleted), `scraper_runs`/`listing_runs` (execution tracking), `price_observations` (the price history, FK'd to its listing and run), `trigger_requests`, `alert_rules`/`alert_events`. Every table uses a `UUID` primary key and real, enforced foreign keys - don't reintroduce free-text columns (e.g. a raw `store_name` string) where a FK to `stores`/`products` already exists. Every table/column name is English - see README.md's "Database Schema" section; `pt-BR` only lives in UI copy (`src/core/i18n.py`), never the schema.
* **Alerting (`src/alerts/`):** A separate domain, decoupled from orchestration. `PriceEngine` accepts an optional `on_price_saved: Callable[[PriceContract, str], Awaitable[None]]` hook (the second argument is the newly-saved `price_observations.id`), called right after each price is persisted; `main.py` wires this to `AlertDispatcher.handle_price`. `PriceEngine` depends only on that `Callable` type - it never imports `src/alerts` - so orchestration stays decoupled from notification internals. `AlertEvaluator` is pure (no I/O) and takes the previous known price as an explicit argument rather than fetching history itself, keeping it fixture-testable like scraper `parse()` methods. `AlertRule` matches on `gpu_model_id`/`store_id` (resolved ids), not free-text brand/model strings.

## 7. QA Strategy & Testing Gates

The project adheres to a strict Testing Pyramid:

* **Unit Tests (>= 95% Coverage):** Must test contracts and parsers. Provide static HTML fixtures in `/tests/fixtures/` to test `parse()` methods without I/O.
* **Integration Tests:** Use mocked HTTP responses (`respx`), mocked browser contexts, and the shared `pricing_test` PostgreSQL database (truncated per-test, see `TESTING.md`) to test the Engine and Repositories.
* **Quality Gates:** Code must pass `mypy`, `black`, and `ruff` before acceptance. Smoke tests (hitting real URLs) must be isolated and never run automatically in CI/CD.
* **Agent Mandate:** Before delivering any task or marking it as successfully complete, the agent MUST run the full test suite (`pytest`) and verify that all tests pass. If tests fail, the agent must fix the broken code or tests before concluding its turn.

## 8. Agent Operations & Validated Commands

To prevent repeated trial-and-error when interacting with the Docker environment and Windows host, agents MUST strictly adhere to the following validated command patterns:

### 8.1 Testing Code Inside the Orchestrator Container
The orchestrator's entrypoint (`entrypoint.orchestrator.sh`) already starts Xvfb on `:99` and waits for it to be ready before launching `main.py` as PID 1 - so headed Playwright works fine for anything the entrypoint itself runs. The catch: `docker exec` does **not** inherit PID 1's environment, so a bare `docker exec pricing_orchestrator python <script.py>` will fail with `Missing X server or $DISPLAY` even though Xvfb is running. Pass `DISPLAY` explicitly instead:
```bash
docker exec -e DISPLAY=:99 pricing_orchestrator python <script.py>
```
Don't reach for `xvfb-run` here - it would spin up a second, redundant X server rather than reusing the one the container's already running.

If you ever see `Fatal server error: Server is already active for display 99` in `docker logs` right after a `docker restart` (as opposed to a full recreate), that's `/tmp`'s stale Xvfb lock/socket surviving the restart - `entrypoint.orchestrator.sh` clears both before starting Xvfb specifically to prevent this; if it recurs, check that cleanup step first.

### 8.2 Rebuilding the Orchestrator
Source files (`/src`) are **copied** into the orchestrator image during build, not mounted via volumes (only `/data` and `config.toml` are mounted). If you modify any `.py` file, you MUST rebuild the container for the changes to take effect:
```bash
docker compose build orchestrator && docker compose up -d --force-recreate orchestrator
```

### 8.3 Reading Docker Logs
`docker logs pricing_orchestrator` works normally and shows full stdout/stderr - it is not swallowed. `data/orchestrator.log` (volume-mounted, so readable from the host too) has the same content via `src/core/logging_setup.py`'s file handler. Either works; `docker logs --since 1m` is usually the fastest way to isolate a specific boot's output when the container has restarted multiple times.

### 8.4 Querying PostgreSQL Directly
`psql` is available inside the `db` container (not the orchestrator):
```bash
docker exec pricing_db psql -U pricing -d pricing -c "
    SELECT po.*, s.slug AS store_name, l.product_url, l.search_keyword, p.name AS model
    FROM price_observations po
    JOIN listings l ON l.id = po.listing_id
    JOIN stores s ON s.id = l.store_id
    JOIN products p ON p.id = l.product_id
    LIMIT 5;
"
```
Swap `-d pricing` for `-d pricing_dev`/`-d pricing_test` to check the other environments (see README.md's "Dev vs. Production Data"). Store/brand/model are not inline columns on `price_observations` (see the schema note in §6) - they only exist behind a JOIN through `listings`/`products`/`brands`/`stores`.

On Windows with Git Bash, `docker exec ... -f /tmp/...`-style paths get mangled by MSYS path conversion; prefix the command with `MSYS_NO_PATHCONV=1` when passing a literal container-side path (e.g. for `pg_dump -f /tmp/backup.dump`).

## 9. Git Flow & Branching Strategy

The project follows a three-tier Git Flow. Agents MUST branch from `develop` (never from `main` or `staging`) when starting new work, unless explicitly doing a hotfix (see below).

### 9.1 Long-Lived Branches
* **`main`** — Production. Only receives merges from `staging` (releases) or `hotfix/*` branches. Never commit directly.
* **`staging`** — Homologation/QA. Receives merges from `develop` when a batch of work is ready for pre-production validation.
* **`develop`** — Integration branch for active development. All feature/fix/chore branches are created from and merged back into `develop`.

### 9.2 Working Branches & Naming Convention
Create working branches from `develop` using `<category>/<short-kebab-case-description>`, e.g. `feat/amazon-spapi-scraper`, `fix/postgres-connection-leak`, `chore/bump-playwright-version`.

| Category   | Use for |
|------------|---------|
| `feat`     | New features or capabilities (e.g. a new scraper, a new alert channel) |
| `fix`      | Bug fixes in `develop`/`staging` that are not production-critical |
| `hotfix`   | Urgent production bug fixes — branched from `main` instead of `develop` (see 9.3) |
| `chore`    | Maintenance: dependency bumps, config changes, tooling, refactors with no behavior change |
| `docs`     | Documentation-only changes (README, TESTING.md, AGENTS.md, etc.) |
| `test`     | Adding or improving tests without changing production behavior |
| `refactor` | Internal restructuring with no functional change (larger than a `chore`) |
| `perf`     | Performance improvements |
| `ci`       | CI/CD pipeline or GitHub Actions changes |

### 9.3 Hotfix Flow (exception to "branch from develop")
For urgent production-breaking bugs: branch `hotfix/<description>` directly from `main`, fix, then merge into **both** `main` (immediate release) and `develop` (so the fix isn't lost on the next `develop` → `staging` → `main` promotion).

### 9.4 Promotion Flow
```
feat/*, fix/*, chore/*, docs/*, test/*, refactor/*, perf/*, ci/*
        │  (PR + review)
        ▼
     develop  ──────────────►  staging  ──────────────►  main
        ▲   (PR, when ready        (PR, after homologation
        │    for homologation)      passes)
        │
   hotfix/*  ── (direct PR to main, then back-merged into develop)
```

* Never merge a working branch directly into `staging` or `main` — it must land on `develop` first (hotfixes excepted).
* Commit messages follow Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`, `perf:`, `ci:`) matching the branch category, consistent with this repo's existing git history.
