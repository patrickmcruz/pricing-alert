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

## 🛠️ Project Structure

```text
/gpu-price-tracker
├── /src
│   ├── /core           # Shared abstractions (BaseScraper, BrowserFactory, config, contracts, registry)
│   ├── /scrapers      # Product page scraping logic (Kabum, Terabyte, etc.); self-register via @register_scraper
│   ├── /engine         # APScheduler orchestration and execution
│   ├── /repositories   # SQLite persistence layer (Repository Pattern)
│   ├── /alerts         # Alerting domain: rules, evaluation, notification delivery
│   └── /ui             # Streamlit Dashboard
├── /data
│   ├── /selectors      # Externalized CSS classes in TOML
│   └── /locales        # i18n localization JSON dictionaries
├── /scripts
│   └── seed_db.py      # Seeds target URLs into the DB for testing
├── config.toml         # App environment configurations
└── pyproject.toml      # Project dependencies and tool configurations
```

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
The application uses the `APP_ENV` environment variable to determine which block in `config.toml` to load. By default, it loads `develop` (which uses `data/prices_dev.db`).

### 3. Running the Orchestrator
Before the scrapers can run, they need target URLs. 

```bash
# 1. (Optional) Seed the database manually, or let the Spiders discover URLs
python scripts/seed_db.py

# 2. Start the Orchestrator
python main.py
```
The orchestrator uses `APScheduler` to trigger the scrapers based on cron configurations (currently stubbed to test every minute).

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

The application is fully containerized using Docker and Docker Compose. The architecture is split into two independent services that share data via Docker Volumes:

1. **`orchestrator`**: Runs the background scraping engine (`main.py`) with Playwright Chromium bundled.
2. **`dashboard`**: Runs the Streamlit user interface (`Dashboard.py`) and exposes it on port `8501`.

Both containers share the `./data` directory (which holds the SQLite database, CSS selectors, and i18n locales) and the `./config.toml` file, meaning you can edit configurations locally and have them instantly reflected in the containers.

To start the application:
```bash
# 1. Build the images (this downloads Chromium for the orchestrator)
docker-compose build

# 2. Start the services in the background
docker-compose up -d
```
The Dashboard container natively checks for the Orchestrator to start first and runs its own `curl` healthchecks.
Once running, simply navigate to `http://localhost:8501` to view your dashboard!

### Troubleshooting Docker Workflows

**1. Code Changes Not Appearing in Docker?**
The `docker-compose.yml` mounts `./data` and `./config.toml` as volumes. This means changes to these files/folders take effect immediately. However, the `./src` directory is *copied* during the Docker image build process. 
If you modify any Python files (`.py`), you must **rebuild** the image for the changes to apply:
```bash
docker compose up -d --build
```
*(Running `docker compose up -d --force-recreate` will only recreate the container from the old image, it will not pull in your new code).*

**2. Seed Script Not Showing in Dashboard?**
When running `python scripts/seed_db.py` locally without specifying an environment, it defaults to the `develop` environment (saving to `data/prices_dev.db`). However, the Docker containers run with `APP_ENV=production` and read from `data/prices.db`.
To properly seed the production database that Docker uses, run:
```bash
# Windows PowerShell
$env:APP_ENV="production"; python .\scripts\seed_db.py

# Linux / Mac
APP_ENV=production python scripts/seed_db.py
```
After seeding, restart the orchestrator (`docker compose restart orchestrator`) so it immediately fetches the new URLs.

---

## 🧪 Testing and Quality Assurance

We strictly enforce a test-driven workflow.
- **Run Unit Tests**: `pytest tests/unit`
- **Run E2E/Integration Tests**: `pytest tests/e2e` and `pytest tests/integration`
- **Run Static Type Checking**: `mypy src tests scripts`

When writing tests for parsers, use the static HTML files provided in `tests/fixtures/`. You should never mock the network layer to test a parser; simply pass the fixture HTML string into `parse()`.

---

## 💡 Adding a New Store Scraper

1. Create `src/scrapers/newstore.py` inheriting from `BaseScraper`, and decorate the class with `@register_scraper` (`src/core/registry.py`).
2. Create `data/selectors/newstore.toml` with `[v1]` selectors (unless the store has a REST API to hit directly, like Mercado Livre - see `transport_type` on `BaseScraper`).
3. Implement `async def fetch()` using the injected client (`Page` for `transport_type = "browser"`, `httpx.AsyncClient` for `"http"`).
4. Implement `def parse()` to extract data and return a `PriceContract`.
5. Add `"enabled": true` for the store in `data/target-stores-list.json`.

That's it - `src/scrapers/__init__.py` auto-imports every module in the package, which triggers the `@register_scraper` decorator, so `main.py` never needs to be touched.
