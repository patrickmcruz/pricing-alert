# Phase 4: Orchestration & Scheduling Engine Implementation Plan

This plan details the steps to build the central Orchestration Engine for the GPU Price Tracker, strictly adhering to the requirements laid out in Artifact 5.

## Proposed Changes

---

### Core Orchestration Logic

#### [NEW] [src/engine/scheduler.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/engine/scheduler.py)
We will implement the `PriceEngine` class which uses `APScheduler` (`AsyncIOScheduler`).
- **Dependency Injection**: It will accept `scheduler`, `repository`, and `client_factory` in its constructor. It will not instantiate any external services directly.
- **`register_scraper`**: Will maintain a dictionary of `BaseScraper` strategies, keyed by `store_name`.
- **`run_scraper`**: Will orchestrate a single job execution for a store. It will request a client from the factory, iterate over the target keywords, await `scraper.execute()`, and pass the resulting data to `repository.save_prices()`. It ensures resources are properly released using `finally`.
- **`build_schedule`**: Will parse the `StoreConfig` cron definitions (e.g., `"14:30"`) and register the `run_scraper` executions dynamically into the `AsyncIOScheduler` using `CronTrigger`.

---

### Integration Tests

#### [NEW] [tests/integration/test_engine.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/tests/integration/test_engine.py)
We will implement integration tests for `PriceEngine` using `pytest`.
- We will mock the `PriceRepository` and `client_factory`.
- We will mock a `BaseScraper` implementation.
- We will verify that `build_schedule()` correctly registers jobs.
- We will verify that `run_scraper()` correctly coordinates fetching, parsing, and persistence, and correctly handles errors to prevent orchestration termination.

## User Review Required

> [!IMPORTANT]
> The orchestrator relies on parsing the `"HH:MM"` `cron_times` string from `StoreConfig`. I plan to use `apscheduler`'s `CronTrigger` to explicitly schedule jobs based on those parsed integers (hour and minute).
> 
> *Do you approve this Phase 4 implementation strategy?*

## Verification Plan

### Automated Tests
- We will execute the Pytest suite specifically targeting `tests/integration/test_engine.py` to prove that the orchestrator coordinates injected dependencies flawlessly without real I/O.
