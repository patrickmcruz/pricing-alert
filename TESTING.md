# Testing Strategy & Automated Tests

This document outlines the testing strategy, architecture, and instructions for running the automated test suite for the GPU Price Tracker application. The project strictly adheres to a Test-Driven Development (TDD) approach, emphasizing test isolation, dependency injection, and deterministic outcomes.

## 1. Test Architecture & Environment Isolation

All tests are executed within an **isolated test environment** to ensure that production and development data are never accidentally modified or polluted.

### Environment Setup (`conftest.py`)
At the start of every `pytest` run, `tests/conftest.py` forces the `APP_ENV` environment variable to `"test"`. 

### The `[test]` Profile (`config.toml`)
The application relies on `config.toml` to load its settings. Under the `[test]` block, the database path is strictly set to `:memory:`. 
For repository-specific unit tests, we utilize `pytest`'s built-in `tmp_path` fixture to spin up dedicated file-based SQLite databases that live only for the duration of a single test.

---

## 2. The Testing Pyramid

The project implements a testing pyramid containing Unit, Integration, and End-to-End (E2E) tests.

### A. Unit Tests (`tests/unit/`)
Unit tests cover isolated components without relying on network I/O or live databases. They run instantly and are highly deterministic.
- **Parsers (`test_parsers.py`)**: Tests the extraction logic (BeautifulSoup + CSS Selectors). Real HTML payloads are cached locally as static files in `tests/fixtures/`. The tests assert that exact metrics (`price_cash`, `price_installments`, `installment_count`, etc.) are reliably extracted.
- **Repositories (`test_repository.py`)**: Uses temporary local SQLite files (`tmp_path`) to ensure table creation, schema migrations, and SQL queries execute correctly.
- **Config (`test_config.py`)**: Verifies the core configuration loader switches environments properly.
- **Spiders & Orchestrators**: Verify internal routing and data-shuffling algorithms.

### B. Integration Tests (`tests/integration/`)
Integration tests ensure that the various standalone components interface correctly. 
- **Pipeline Test (`test_pipeline.py`)**: Tests the entire data pipeline. It orchestrates the `PriceEngine`, utilizes a mocked Playwright HTTP client to simulate network responses, fires a concrete Scraper instance, and verifies that the extracted data is properly persisted to the SQLite repository.

### C. End-to-End (E2E) / Smoke Tests (`tests/e2e/`)
E2E tests interact with the actual external ecosystem.
- **Smoke Tests (`test_smoke.py`)**: Marked with `@pytest.mark.e2e`. These tests spin up a real Playwright headless browser, execute a live network request to an actual store (e.g., Kabum), and parse live DOM trees. They prove that the external world hasn't drifted out of alignment with our internal CSS selectors.

---

## 3. Running the Test Suite

The test runner is configured using `pyproject.toml`.

### Run Core Tests (Excluding E2E)
To run all unit and integration tests (fast and fully isolated from the network):
```bash
pytest tests/ -m "not e2e"
```

### Run Tests with Coverage Report
To view line-by-line coverage for the application core (ignoring UI components):
```bash
pytest tests/ -m "not e2e" --cov=src
```
*Note: The target is always >= 90% coverage for core abstractions and parsers.*

### Run Live End-to-End Tests
To execute the live-network smoke tests:
```bash
pytest tests/e2e/test_smoke.py -v
```

---

## 4. How to Write New Tests

If you are expanding the application or adding a new store parser, follow these rules:

1. **Add Static Fixtures:** Download the raw HTML of the product or search grid you wish to parse and save it in `tests/fixtures/{store_name}_mock.html`.
2. **Never Mock Selectors:** Test the *real* extraction logic against the *real* HTML using your TOML selector files.
3. **Use AsyncMock & MagicMock:** If a component requires network access (like `BrowserFactory`), inject a mock client via its constructor instead of reaching out to the live internet.
4. **Agent Mandate:** Always execute the test suite to ensure all tests pass before completing your work.

## 5. Troubleshooting
If you encounter `ValueError: I/O operation on closed pipe` warnings on Windows during test tear-down, these are safely ignored. They are harmless artifacts of Playwright closing subprocess pipes under the `asyncio` Proactor event loop. A `filterwarnings` directive in `pyproject.toml` is used to actively suppress them.
