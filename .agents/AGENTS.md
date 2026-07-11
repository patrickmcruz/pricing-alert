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
* **Database:** SQLite3 (via Repository Pattern)
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
│   │   └── utils.py                  # Shared helper functions
│   ├── /spiders                      # Discovery Engine (crawls grids for URLs)
│   ├── /scrapers                     # Scraper Engine (parses specific Product Pages)
│   ├── /engine                       # Orchestration (scheduler.py, discovery.py)
│   ├── /repositories                 # Persistence layer (SQLite implementation)
│   ├── /ui                           # Streamlit application
│   └── /data
│       └── target-stores-list.json   # Store definitions (Cron configs)
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

## 5. Spider & Scraper Architecture (The Two-Tier Strategy)

The extraction process is strictly divided into two independent engines:

* **Discovery Engine (Spiders):** Responsible for crawling search grids (e.g., searching for "rtx 5070"), extracting URLs, Brands, and Models, and persisting them as `ProductSKU` records in the `target_urls` database table.
* **Scraper Engine (Scrapers):** Concrete scrapers inherit from `BaseScraper` and visit the exact product URLs discovered by the Spiders.

Concrete scrapers must implement strictly separated methods:
1. **`fetch(self, sku: ProductSKU, client: Any) -> str`**: Performs ONLY network I/O. Returns raw HTML. 
2. **`parse(self, document: str, sku: ProductSKU) -> Optional[PriceContract]`**: Performs ONLY data extraction using CSS selectors loaded from the `data/selectors/{store}.toml` file. **Must be 100% deterministic and unit-testable**.
3. **`execute()`**: Orchestrates the fetch and parse pipeline.

**Resilience, Fallbacks & Versioning:** 
Scrapers MUST NOT hardcode CSS classes, IDs, or XPath expressions under any circumstances. If a dynamic or primary selector fails, any fallback selectors MUST also be read dynamically from the corresponding `data/selectors/{store}.toml` file. If a `parse()` method cannot find critical DOM elements using its TOML selectors, it must raise a `SelectorOutdatedException`. The `PriceContract` records the `parser_version` to maintain data lineage.

## 6. Orchestration & Persistence

* **Scheduler (`PriceEngine`):** Responsible for loading `ProductSKU` records from the repository and coordinating execution of the Scrapers. Catches `SelectorOutdatedException` gracefully to prevent batch crashes.
* **Repository Pattern:** Database operations are isolated behind `PriceRepository`. Scrapers never talk to SQLite.

## 7. QA Strategy & Testing Gates

The project adheres to a strict Testing Pyramid:

* **Unit Tests (>= 95% Coverage):** Must test contracts and parsers. Provide static HTML fixtures in `/tests/fixtures/` to test `parse()` methods without I/O.
* **Integration Tests:** Use mocked HTTP responses (`respx`), mocked browser contexts, and temporary in-memory SQLite databases to test the Engine and Repositories.
* **Quality Gates:** Code must pass `mypy`, `black`, and `ruff` before acceptance. Smoke tests (hitting real URLs) must be isolated and never run automatically in CI/CD.
* **Agent Mandate:** Before delivering any task or marking it as successfully complete, the agent MUST run the full test suite (`pytest`) and verify that all tests pass. If tests fail, the agent must fix the broken code or tests before concluding its turn.

## 8. Agent Operations & Validated Commands

To prevent repeated trial-and-error when interacting with the Docker environment and Windows host, agents MUST strictly adhere to the following validated command patterns:

### 8.1 Testing Code Inside the Orchestrator Container
The orchestrator relies on Playwright, which requires an X11 server to run headed browsers. If you run `python` directly via `docker exec`, it will crash with a `TargetClosedError` due to a missing `$DISPLAY`.
**Always use `xvfb-run`:**
```bash
docker exec pricing_orchestrator xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" python <script.py>
```

### 8.2 Rebuilding the Orchestrator
Source files (`/src`) are **copied** into the orchestrator image during build, not mounted via volumes (only `/data` and `config.toml` are mounted). If you modify any `.py` file, you MUST rebuild the container for the changes to take effect:
```bash
docker-compose up -d --build orchestrator
```

### 8.3 Reading Docker Logs on Windows
In PowerShell, standard Unix commands like `tail` or `grep` might fail. The orchestrator's stdout is swallowed by `xvfb-run`, meaning `docker logs pricing_orchestrator` will be empty.
**To read logs, parse the file directly via PowerShell:**
```powershell
# Tail logs:
Get-Content data/orchestrator.log -Tail 100

# Grep logs:
Select-String -Path data/orchestrator.log -Pattern "keyword"
```

### 8.4 Querying SQLite Directly
The `sqlite3` CLI is not installed inside the `python:3.11-slim` container by default. Instead of trying to install it or running `docker exec sqlite3`, query the database locally from the host using Python (since `data/` is volume-mapped):
```powershell
python -c "
import sqlite3
conn = sqlite3.connect('data/prices.db')
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT * FROM prices LIMIT 5;').fetchall()
for row in rows: print(dict(row))
"
```
