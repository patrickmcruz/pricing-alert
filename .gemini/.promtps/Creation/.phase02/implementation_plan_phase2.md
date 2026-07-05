# Phase 2: Persistence Layer Implementation Plan

This plan details the steps to build the persistence layer for the GPU Price Tracker, adhering to the Dependency Inversion and Repository Pattern constraints specified in `AGENTS.md` and Artifact 5.

## Proposed Changes

---

### Abstract Repository Interface

#### [NEW] [src/repositories/base_repository.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/repositories/base_repository.py)
We will create the `PriceRepository` abstract base class. As defined in Artifact 5, the orchestration engine expects an asynchronous interface to persist data without knowing the underlying database technology.
- **`save_prices(prices: List[PriceContract]) -> None`**: Abstract method to save scraped data.
- **`get_prices_by_keyword(keyword: str) -> List[PriceContract]`**: Abstract method for future UI data retrieval.

---

### SQLite Concrete Implementation

#### [NEW] [src/repositories/sqlite_repository.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/repositories/sqlite_repository.py)
We will implement `SQLitePriceRepository` inheriting from `PriceRepository`.
- It will execute a schema creation script on initialization to ensure the `prices` table exists.
- The `prices` table schema will directly mirror the `PriceContract` Pydantic model (using `TEXT` for UUID/Strings/URLs/Timestamps, `DECIMAL` for monetary fields, and `BOOLEAN` for availability).
- It will implement `save_prices` to efficiently insert batches of normalized data.

---

### Dependency Updates

#### [MODIFY] [requirements.txt](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/requirements.txt)
Artifact 5 explicitly dictates that `PriceEngine` orchestrator awaits repository persistence: `await self.repository.save_prices(prices)`. 
To ensure non-blocking disk I/O within our `asyncio` event loop, we need to add `aiosqlite` to our production dependencies. It provides an async, awaitable interface to standard `sqlite3`.
- **Action**: Append `aiosqlite` to the file.

---

## User Review Required

> [!IMPORTANT]
> The orchestrator expects async persistence (`await save_prices()`). To achieve this natively with SQLite without blocking the event loop, I propose adding the standard open-source library `aiosqlite` to our dependencies. Do you approve this addition and the overall schema plan?

## Verification Plan

### Automated Tests
- No automated tests will be run *during* generation, but the architecture strictly supports mocking the `PriceRepository` for Phase 4 orchestration testing. Phase 6 QA will include integration tests against a temporary SQLite database to verify data mapping between `PriceContract` and SQLite.

### Manual Verification
- Verify that `aiosqlite` is correctly added.
- Review the implemented schema to ensure no data loss occurs when saving `PriceContract` structures.
