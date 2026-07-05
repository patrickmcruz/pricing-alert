# GPU Price Tracker 🚀

A highly modular, resilient, and test-driven web scraping orchestrator built to monitor GPU prices (specifically RTX 5070 and RTX 5070 Ti) across major Brazilian e-commerce stores.

## Welcome, New Developers!

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
- **Gitflow Configuration**: All app settings are defined in `config.toml` (using native `tomllib`), providing distinct `[develop]`, `[staging]`, and `[production]` environments.

---

## 🛠️ Project Structure

```text
/gpu-price-tracker
├── /src
│   ├── /core           # Shared abstractions (BaseScraper, BrowserFactory, config, contracts)
│   ├── /spiders        # Grid-level discovery logic
│   ├── /scrapers       # Product page scraping logic (Kabum, Terabyte, etc.)
│   ├── /engine         # APScheduler orchestration and execution
│   ├── /repositories   # SQLite persistence layer (Repository Pattern)
│   └── /ui             # Streamlit Dashboard
├── /data
│   └── /selectors      # Externalized CSS classes in TOML
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
# 1. Seed the development database with real target URLs
python scripts/seed_db.py

# 2. Start the Orchestrator
python main.py
```
The orchestrator uses `APScheduler` to trigger the scrapers based on cron configurations (currently stubbed to test every minute).

### 4. Viewing the Dashboard
To see the scraped prices:
```bash
streamlit run src/ui/dashboard.py
```

---

## 🧪 Testing and Quality Assurance

We strictly enforce a test-driven workflow.
- **Run Unit Tests**: `pytest tests/unit`
- **Run Static Type Checking**: `mypy src tests scripts`

When writing tests for parsers, use the static HTML files provided in `tests/fixtures/`. You should never mock the network layer to test a parser; simply pass the fixture HTML string into `parse()`.

---

## 💡 Adding a New Store Scraper

1. Create `src/scrapers/newstore.py` inheriting from `BaseScraper`.
2. Create `data/selectors/newstore.toml` with `[v1]` selectors.
3. Implement `async def fetch()` using the injected Playwright `client`.
4. Implement `def parse()` to extract data and return a `PriceContract`.
5. Register it in `main.py` inside `engine.register_scrapers()`.
