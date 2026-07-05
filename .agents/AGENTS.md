# Agent Context & Blueprint: GPU Price Tracker (Test-Driven Architecture)

You are a Senior Full-Stack Software Architect and Data Engineer. Your objective is to build and maintain a modular, single-user, 100% open-source web application for automated GPU price monitoring (specifically GeForce RTX 5070 and RTX 5070 Ti) across Brazilian e-commerce stores.

## 1. Architectural Philosophy & Constraints
* **Test-Driven & Deterministic:** The system must be designed for maximum testability. Business logic, parsing, and orchestration must be independently testable without network access, browser automation, or a live database.
* **Separation of Concerns:** Network I/O, HTML parsing, orchestration, and persistence are strictly decoupled.
* **Dependency Injection & IoC:** Never instantiate HTTP clients, Playwright contexts, or databases inside the scrapers or the scheduler. Use factories and inject them.
* **No External Dependencies:** The app runs entirely locally. No paid APIs.

## 2. Mandatory Technology Stack
* **Language:** Python 3.11+
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
│   │   ├── contract.py               # Pydantic data models
│   │   ├── base_scraper.py           # Abstract Base Class
│   │   ├── config.py                 # Application configuration
│   │   ├── browser.py                # Playwright factory
│   │   ├── http_client.py            # HTTPX client factory
│   │   └── utils.py                  # Shared helper functions
│   ├── /scrapers                     # One scraper strategy per store
│   ├── /engine                       # Orchestration (scheduler.py)
│   ├── /repositories                 # Persistence layer (SQLite implementation)
│   ├── /ui                           # Streamlit application
│   └── /data
│       └── target-stores-list.json   # Store definitions
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
* Timestamps must use timezone-aware UTC (`datetime.now(timezone.utc)`).

## 5. BaseScraper Architecture (The Strategy)

Concrete scrapers must inherit from `BaseScraper` and implement strictly separated methods:

1. **`fetch(self, keyword: str, client: Any) -> str`**: Performs ONLY network I/O. Returns raw HTML. The `client` (HTTPX or Playwright) is injected.
2. **`parse(self, document: str, keyword: str) -> List[PriceContract]`**: Performs ONLY data extraction. **Must be 100% deterministic and unit-testable** using static HTML fixtures without network access.
3. **`execute()`**: Orchestrates the jitter, fetch, and parse pipeline.

## 6. Orchestration & Persistence

* **Scheduler (`PriceEngine`):** Responsible only for registering scrapers, loading schedules from `StoreConfig`, coordinating execution, and passing results to the repository. Receives `repository` and `client_factory` via dependency injection.
* **Repository Pattern:** Database operations are isolated behind `PriceRepository`. Scrapers never talk to SQLite.
* **Isolation:** If one scraper fails during execution, exceptions must be handled so that other scheduled jobs are not interrupted. Resources (clients/contexts) must be properly released.

## 7. QA Strategy & Testing Gates

The project adheres to a strict Testing Pyramid:

* **Unit Tests (>= 95% Coverage):** Must test contracts and parsers. Provide static HTML fixtures in `/tests/fixtures/` to test `parse()` methods without I/O.
* **Integration Tests:** Use mocked HTTP responses (`respx`), mocked browser contexts, and temporary in-memory SQLite databases to test the Engine and Repositories.
* **Quality Gates:** Code must pass `mypy`, `black`, and `ruff` before acceptance. Smoke tests (hitting real URLs) must be isolated and never run automatically in CI/CD.
