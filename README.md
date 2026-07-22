# GPU Price Tracker 🚀

A highly modular, resilient, and test-driven web scraping orchestrator built to monitor GPU prices (specifically RTX 5070 and RTX 5070 Ti) across major Brazilian e-commerce stores.

## Welcome!

If you are joining the project, this document will help you understand our architectural principles and how to run, test, and contribute to the application. Our architecture enforces a strict **Separation of Concerns**, ensuring that business logic, network retrieval, HTML parsing, orchestration, and persistence never tightly couple.

---

## 🏗️ Architecture & Philosophy

The system uses a **Two-Tier Extraction Strategy**:
1. **Discovery Engine (Spiders)**: Responsible for crawling search grids to find Product URLs and persisting them as `ProductSKU` objects.
2. **Scraper Engine (Scrapers)**: Navigates to the specific URLs provided by the Spiders and extracts the localized price data.

### Key Architectural Constraints
- **100% Deterministic Parsers**: Our `parse()` methods in `BaseScraper` implementations perform zero network I/O. They accept an HTML string and output a strictly typed `PriceContract` (using Pydantic V2).
- **Externalized Selectors**: We NEVER hardcode CSS classes in Python. All selectors are stored in `data/selectors/{store}.toml`. If a store changes its UI (e.g., switches to Tailwind), we simply bump the parser version in Python and add a new `[v2]` block to the TOML file!
- **Playwright Network Layer**: Since many modern stores (like Kabum) are Single Page Applications built with React/Next.js, we use `BrowserFactory` (Playwright) to retrieve the DOM asynchronously.
## Lojas Protegidas e Integração de APIs

Algumas lojas possuem defesas antibot (ex: Kabum). Para essas, nosso ecossistema utiliza o Playwright (`BrowserFactory`) para simular renderização de um ambiente humano invisível (`headless=true`).

Entretanto, o Mercado Livre possui firewalls de última geração (Datadome/Cloudflare) em suas Lojas Oficiais. Para o **Mercado Livre**, contornamos o bloqueio de raspagem de DOM adotando uma arquitetura 100% nativa utilizando a **API Oficial Pública do Mercado Livre** via tokens OAuth 2.0.

Para que o scraper do Mercado Livre funcione, você precisa preencher o `.env` com suas credenciais de parceiro desenvolvedor. Para o passo-a-passo detalhado, leia a [Documentação Oficial do Mercado Livre Scraper](docs/scrapers/mercadolivre.md).

## Configuração do config.toml
- **Gitflow Configuration**: All app settings are defined in `config.toml` (using native `tomllib`), providing distinct `[develop]`, `[staging]`, and `[production]` environments.

---

## 📚 Central de Documentação

Esta base de código conta com uma suíte de documentação enterprise completa. Acesse os guias detalhados abaixo:

| Documento | Descrição |
| :--- | :--- |
| 🗄️ [**DER / MER & Banco de Dados**](docs/database/DER_MER.md) | Modelo Entidade-Relacionamento (MER), Diagrama ER físico em Mermaid, Dicionário de Dados e Schemas JSONB para hardware (GPUs, Placas Mãe, RAM). |
| 🏗️ [**Visão Geral da Arquitetura**](docs/architecture/OVERVIEW.md) | Diagramas de componentes e de sequência mostrando a interação entre orquestrador, scrapers, repositórios e alertas. |
| 🔍 [**Title Parsers & Seletores**](docs/architecture/PARSERS.md) | Motor de parsing `TitleParserRegistry` e versionamento dinâmico de seletores CSS via arquivos TOML em `data/selectors/`. |
| 🛠️ [**Guia de Expansão de Categorias**](docs/guides/ADDING_NEW_HARDWARE_CATEGORY.md) | Passo a passo para adicionar suporte a novas categorias de hardware (Processadores, Placas Mãe, Memórias RAM, SSDs). |
| 🛒 [**Integração Mercado Livre Scraper**](docs/scrapers/mercadolivre.md) | Guia de autenticação e consumo da API oficial pública do Mercado Livre via OAuth 2.0. |

---

## 🛠️ Project Structure

```text
/gpu-price-tracker
├── /src
│   ├── /core           # Shared abstractions (BaseScraper, BrowserFactory, config, contracts, registry)
│   ├── /scrapers      # Product page scraping logic (Kabum, Terabyte, etc.); self-register via @register_scraper
│   ├── /engine         # APScheduler orchestration and execution
│   ├── /db
│   │   └── schema.py   # Single source of truth for the PostgreSQL schema (see "Database Schema" below)
│   ├── /repositories   # Persistence layer (PostgreSQL/asyncpg implementation, Repository Pattern per entity)
│   ├── /alerts         # Alerting domain: rules, evaluation, notification delivery
│   └── /ui             # Streamlit Dashboard
├── /data
│   ├── /selectors      # Externalized CSS classes in TOML
│   ├── /locales        # i18n localization JSON dictionaries
│   └── /backups        # Timestamped pg_dump snapshots (scripts/backup_db.py) - gitignored
├── /scripts
│   ├── migrate_target_urls.py       # One-time: imports data/target_urls.json into the DB catalog
│   ├── migrate_git_history_prices.py # Recovers price history from every historical git revision of the old SQLite .db files
│   ├── seed_db.py                    # Seeds a handful of mock target URLs into the DB for testing
│   └── trim_dev_listings.py          # Caps tracked listings per (store, chipset) in dev for fast test scrapes
├── config.toml         # App environment configurations
└── pyproject.toml      # Project dependencies and tool configurations
```

---

## 🗄️ Database Schema

All persistence is PostgreSQL (via `asyncpg`), with a single shared schema module (`src/db/schema.py`) instead of each repository owning its own tables. Every table uses a `UUID` primary key, and foreign keys are enforced natively by Postgres. Every identifier - table and column - is English; any Portuguese only shows up in `pt-BR` UI copy via `src/core/i18n.py`, never in the schema.

| Table | Purpose |
|---|---|
| `stores` | Retailers this app tracks (kabum, mercado-livre, terabyte, ...) |
| `categories`, `brands`, `products` | Normalized product catalog: category (e.g. "GPU"), board partner/brand, and the specific brand+category+variant combination, with category-specific attributes (chipset, VRAM...) in `products.specs` (JSONB) |
| `listings` | A tracked product URL at a store, FK'd to its `product`; soft-deleted (`is_active = false`) instead of hard-deleted so price history is never orphaned |
| `scraper_runs`, `listing_runs` | Execution tracking: one row per store run, one row per SKU attempt within it |
| `price_observations` | The actual price history - FK'd to its `listings` row and originating `scraper_runs` row, no duplicated store/brand/model text |
| `trigger_requests` | "Run now" requests queued by the dashboard, consumed by the orchestrator |
| `alert_rules`, `alert_events` | User-defined price-drop rules (matched by `product_id`/`store_id`, not free-text) and the events they fired, each FK'd to the `price_observations` row that triggered it |

To (re)initialize the schema against any DSN, call `src.db.schema.initialize_schema(dsn)` - it's idempotent (`CREATE TABLE IF NOT EXISTS`), so it's safe to call from `main.py`, a Streamlit page, or a script. `main.py` also re-asserts the full `data/target_urls.json` catalog as active on every orchestrator boot (idempotent upsert), so production's SKU set self-heals even if something got deactivated - see "Dev vs. Production Data" below.

### Dev vs. Production Data

`config.toml`'s `[develop]`/`[staging]`/`[production]`/`[test]` blocks each point at their **own** Postgres database on the same server (`pricing_dev`, `pricing_staging`, `pricing`, `pricing_test`) - trimming or resetting your local dev data can never touch production. `scripts/init_test_db.sql` creates `pricing_test`/`pricing_dev` automatically the first time the `db` container's volume is created.

- **Production** (`docker compose up`, `APP_ENV=production`): always ends up with the full catalog from `data/target_urls.json` - the orchestrator's boot-time discovery step keeps it that way on every restart.
- **Local dev/testing** (`APP_ENV=develop`): seed once with `scripts/migrate_target_urls.py`, then trim it down for fast iteration:
  ```bash
  APP_ENV=develop python scripts/trim_dev_listings.py 1   # keep at most 1 per (store, chipset)
  ```
  `trim_dev_listings.py` refuses to run against `APP_ENV=production` - production is meant to keep every listing it has ever discovered.

---

## 🚀 Getting Started

### 1. Installation
We use `pyproject.toml` to manage dependencies. Ensure you have Python 3.11+.

```bash
# Create a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows

# Install the app and development tools
pip install -e .[dev]

# Install Playwright browser binaries
playwright install chromium
```

### 2. Environment Setup
The application uses the `APP_ENV` environment variable to determine which block in `config.toml` to load (`develop`, `staging`, `production`, or `test`), which in turn selects which Postgres database to connect to (`db_host`/`db_port`/`db_name`/`db_user`; the password always comes from the `POSTGRES_PASSWORD` env var, never committed). Defaults to `develop` → the `pricing_dev` database. You need a running Postgres instance reachable at that DSN - the simplest way is `docker compose up -d db` (see "Running with Docker" below), which also creates `pricing_dev`/`pricing_test` automatically alongside `pricing`.

### 3. Running the Orchestrator
Before the scrapers can run, they need target URLs.

```bash
# 1. Seed the full catalog from data/target_urls.json ...
python scripts/migrate_target_urls.py
# ... or seed a small hardcoded mock set instead
python scripts/seed_db.py

# 2. Start the Orchestrator
python main.py
```
The orchestrator uses `APScheduler` to trigger the scrapers based on cron configurations, and re-seeds the full catalog on every boot when `APP_ENV=production` (see "Dev vs. Production Data" above).

**Fast local test scrapes:** a full dev scrape across every discovered listing can be slow. `scripts/trim_dev_listings.py` caps how many listings stay active per (store, chipset) pair, soft-deleting the rest so their price history isn't lost:
```bash
APP_ENV=develop python scripts/trim_dev_listings.py 2   # keep at most 2 per (store, chipset)
```
It refuses to run against `APP_ENV=production` - production is meant to keep every listing it has ever discovered. For a single one-shot run against everything currently active (no scheduler, exits when done), use `python scripts/run_all_scrapers.py`.

### 4. Viewing the Dashboard
To see the scraped prices:
```bash
streamlit run src/ui/Dashboard.py
```
The dashboard features:
- **Dynamic Chart Timelines:** The main graphics default to an aggregated "hour-by-hour" view but allow you to dynamically zoom (drill down) into minute-level scrapes seamlessly.
- **Two-Tier Analytics:** Detailed product views separate analytics for "Cash Price" and "Installment Price", showing minimums, maximums, and volatility for both.
- **Data Filtering:** The raw scraped data grid includes comprehensive filters for all tracked columns.
- **Internationalization (i18n):** Fully localized interface supporting both `pt-BR` and `en-US` seamlessly.

---

## 🐳 Running with Docker

The application is fully containerized using Docker Compose, with three services:

1. **`db`**: PostgreSQL 16, with its own named volume. Creates the `pricing`, `pricing_dev`, and `pricing_test` databases on first boot (`scripts/init_test_db.sql`).
2. **`orchestrator`**: Runs the background scraping engine (`main.py`) with Playwright Chromium bundled, `APP_ENV=production` (→ the `pricing` database). Waits for `db` to report healthy before starting.
3. **`dashboard`**: Runs the Streamlit user interface (`Dashboard.py`) and exposes it on port `8501`. Waits for both `db` and `orchestrator`.

`orchestrator`/`dashboard` share the `./data` directory (CSS selectors, i18n locales, backups) and the `./config.toml` file as volumes - editing those locally takes effect immediately without a rebuild.

To start the application:
```bash
# 1. Build the images (this downloads Chromium for the orchestrator)
docker compose build

# 2. Start every service in the background
docker compose up -d
```
Once running, navigate to `http://localhost:8501` to view your dashboard!

### Troubleshooting Docker Workflows

**1. Code Changes Not Appearing in Docker?**
The `./src` directory is *copied* into the image during build, not mounted. If you modify any Python file, you must **rebuild** the image for the change to apply:
```bash
docker compose up -d --build orchestrator dashboard
```
*(`docker compose up -d --force-recreate` alone only recreates the container from the existing image - it does not pick up new code.)*

**2. Orchestrator Crash-Looping After `docker restart`?**
If you use `docker restart pricing_orchestrator` (rather than a full recreate), the container's `/tmp` survives, including any stale Xvfb lock/socket from the previous run. `entrypoint.orchestrator.sh` clears these before starting Xvfb, so this shouldn't happen anymore - but if you ever see `Missing X server or $DISPLAY` in the logs after a restart, that stale-lock cleanup is the first place to check.

**3. Production Missing SKUs?**
It shouldn't be - `main.py` re-seeds the full `data/target_urls.json` catalog as active on every orchestrator boot when `APP_ENV=production` (idempotent upsert, see "Dev vs. Production Data" above). If you still see fewer SKUs than expected, check `docker logs pricing_orchestrator` for the "Discovery Engine run" boot log line and any errors around it.

**4. Querying the Database Directly**
```bash
docker exec pricing_db psql -U pricing -d pricing -c "SELECT count(*) FROM listings WHERE is_active = true;"
```
Swap `-d pricing` for `-d pricing_dev`/`-d pricing_test` to check the other environments.

---

## 🧪 Testing and Quality Assurance

We strictly enforce a test-driven workflow.
- **Run Unit Tests**: `pytest tests/unit`
- **Run E2E/Integration Tests**: `pytest tests/e2e` and `pytest tests/integration`
- **Run Static Type Checking**: `mypy src tests scripts`

When writing tests for parsers, use the static HTML files provided in `tests/fixtures/`. You should never mock the network layer to test a parser; simply pass the fixture HTML string into `parse()`.

---

## 🌳 Git Flow & Branching Strategy

The project uses a three-tier Git Flow:

| Branch | Purpose |
|---|---|
| `main` | Production. Only receives merges from `staging` (releases) or `hotfix/*` branches - never commit directly. |
| `staging` | Homologation/QA. Receives merges from `develop` when a batch of work is ready for pre-production validation. |
| `develop` | Integration branch for active development. All working branches are created from and merged back into `develop`. |

### Branch Naming
Create working branches from `develop` using `<category>/<short-kebab-case-description>`, e.g. `feat/amazon-spapi-scraper`, `fix/postgres-connection-leak`, `chore/bump-playwright-version`.

| Category | Use for |
|---|---|
| `feat` | New features or capabilities (e.g. a new scraper, a new alert channel) |
| `fix` | Bug fixes in `develop`/`staging` that are not production-critical |
| `hotfix` | Urgent production bug fixes - branched from `main` instead of `develop` |
| `chore` | Maintenance: dependency bumps, config changes, tooling, refactors with no behavior change |
| `docs` | Documentation-only changes (README, TESTING.md, AGENTS.md, etc.) |
| `test` | Adding or improving tests without changing production behavior |
| `refactor` | Internal restructuring with no functional change (larger than a `chore`) |
| `perf` | Performance improvements |
| `ci` | CI/CD pipeline or GitHub Actions changes |

### Promotion Flow
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

Hotfixes are the one exception to "branch from `develop`": for urgent production-breaking bugs, branch `hotfix/<description>` directly from `main`, then merge into **both** `main` (immediate release) and `develop` (so the fix isn't lost on the next promotion). Never merge a working branch directly into `staging` or `main` otherwise - it must land on `develop` first. Commit messages follow Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`, `perf:`, `ci:`) matching the branch category.

---

## 💡 Adding a New Store Scraper

1. Create `src/scrapers/newstore.py` inheriting from `BaseScraper`, and decorate the class with `@register_scraper` (`src/core/registry.py`).
2. Create `data/selectors/newstore.toml` with `[v1]` selectors (unless the store has a REST API to hit directly, like Mercado Livre - see `transport_type` on `BaseScraper`).
3. Implement `async def fetch()` using the injected client (`Page` for `transport_type = "browser"`, `httpx.AsyncClient` for `"http"`).
4. Implement `def parse()` to extract data and return a `PriceContract`.
5. Add `"enabled": true` for the store in `data/target-stores-list.json`.

That's it - `src/scrapers/__init__.py` auto-imports every module in the package, which triggers the `@register_scraper` decorator, so `main.py` never needs to be touched.
