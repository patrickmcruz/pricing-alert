# **ARTIFACT 6: Quality Assurance Strategy and Automated Testing (QA Specification)**

## 1. Overview

The project must adopt a **test-first architecture** in which every component is designed to be independently testable.

The automated test suite must validate:

- data contracts;
- parser correctness;
- orchestration behavior;
- persistence;
- scheduling;
- complete application workflows.

Tests must be deterministic, reproducible, and executable without internet connectivity unless explicitly designated as smoke tests.

---

## 2. Testing Pyramid

The testing strategy follows the classic testing pyramid.

| Level | Purpose | External Dependencies |
|--------|---------|-----------------------|
| Unit | Business logic, contracts, parsers | None |
| Integration | Scheduler, repositories, dependency injection | Mocked |
| End-to-End | Complete workflow | Mocked |
| Smoke | Real websites | Internet |

Smoke tests are optional and must never execute automatically in CI/CD.

---

## 3. Development Dependencies

The agent must create a `requirements-dev.txt` file containing:

| Purpose | Package |
|----------|---------|
| Test framework | `pytest` |
| Async support | `pytest-asyncio` |
| Mocking | `pytest-mock` |
| HTTP mocking | `respx` |
| Coverage | `pytest-cov` |
| Type checking | `mypy` |
| Linting | `ruff` |
| Formatting | `black` |
| UI testing (optional) | `streamlit.testing` or `pytest-playwright` |

---

## 4. Project Structure

```plaintext
/tests
│
├── fixtures/
│     kabum_rtx5070_sample.html
│     mercadolivre_rtx5070_sample.html
│
├── unit/
│     test_contracts.py
│     test_parsers.py
│     test_scheduler.py
│     test_utils.py
│
├── integration/
│     test_repository.py
│     test_engine.py
│
├── e2e/
│     test_pipeline.py
│
└── smoke/
      test_real_store.py
```

---

## 5. Test Isolation

The automated test suite must satisfy the following isolation rules.

### Unit Tests

Must not require:

- internet access;
- Playwright;
- SQLite;
- APScheduler;
- Streamlit.

Only pure Python code may be executed.

---

### Integration Tests

May use:

- mocked repositories;
- mocked HTTP clients;
- mocked browser contexts;
- temporary SQLite databases.

Network access is prohibited.

---

### End-to-End Tests

The complete workflow is executed using:

- mocked HTTP responses;
- static HTML fixtures;
- temporary databases.

No real websites are contacted.

---

### Smoke Tests

Smoke tests are the only tests permitted to access external websites.

They must:

- execute manually;
- never run automatically in CI/CD;
- be clearly marked using Pytest markers.

---

## 6. Fixture Strategy

HTML fixtures are considered immutable snapshots.

Each scraper must include:

- at least one HTML fixture;
- parser unit tests using that fixture;
- expected extraction results.

Fixtures should only be updated when the retailer changes its page structure.

---

## 7. Quality Gates

The project must satisfy the following minimum quality requirements before acceptance.

| Metric | Requirement |
|---------|-------------|
| Unit test coverage | ≥ 95% |
| Type checking | mypy passes |
| Formatting | black passes |
| Linting | ruff passes |
| Unit tests | 100% pass |
| Integration tests | 100% pass |

---

## 8. Continuous Integration

The project must be compatible with GitHub Actions.

The CI pipeline should execute:

1. Ruff
2. Black (check mode)
3. MyPy
4. Unit tests
5. Integration tests
6. End-to-End tests

Smoke tests must not execute automatically.

---

## Implementation Requirements

The agent must ensure that:

- Every public component has automated tests.
- Every scraper includes parser tests using static HTML fixtures.
- Parsing logic is tested independently from network I/O.
- Network operations are mocked using `respx`.
- Browser automation is never required for parser unit tests.
- Repository implementations are tested using temporary SQLite databases.
- The scheduler is tested using mocked repositories and mocked scrapers.
- The orchestration layer is fully testable through dependency injection.
- Tests are deterministic and reproducible.
- No unit, integration, or end-to-end test depends on internet connectivity.
- New functionality introduced by the agent is accompanied by corresponding automated tests.
- CI failures occur whenever formatting, linting, typing, or automated tests fail.
- The test suite remains compatible with local execution and GitHub Actions.