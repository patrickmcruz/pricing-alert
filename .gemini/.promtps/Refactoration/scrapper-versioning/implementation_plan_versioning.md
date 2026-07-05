# Implementation Plan: Config-Driven Versioned Scrapers

Based on our architectural discussion, this plan outlines the steps to refactor our current hardcoded scrapers into a resilient, version-controlled extraction engine. This ensures that when an e-commerce store changes its UI, we can adapt by simply adding a new configuration block instead of rewriting Python code.

## Proposed Changes

---

### 1. Data Contracts & Persistence
#### [MODIFY] [src/core/contract.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/core/contract.py)
- Add `parser_version: str` to `PriceContract`. This ensures every database record carries the lineage of which parser configuration extracted it.

#### [MODIFY] [src/repositories/sqlite_repository.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/repositories/sqlite_repository.py)
- Update the `initialize_schema` method for the `prices` table to include the new `parser_version TEXT` column.
- Update `save_prices` to persist this new attribute.

---

### 2. Externalizing Selectors (The Configs)
#### [NEW] [data/selectors/kabum.toml](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/data/selectors/kabum.toml)
#### [NEW] [data/selectors/terabyte.toml](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/data/selectors/terabyte.toml)
Create TOML files specifically dedicated to CSS selector paths. 

Example for Kabum:
```toml
[v1]
title = "h1"
price_cash = ".finalPrice"
price_installments = ".regularPrice"
out_of_stock = "indisponível"
```

---

### 3. Base Scraper & Exception Handling
#### [MODIFY] [src/core/base_scraper.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/core/base_scraper.py)
- Create a new custom exception: `SelectorOutdatedException`. 
- Implement a helper method `load_selectors(store_name, version)` inside `BaseScraper` that reads the specific TOML block.

---

### 4. Refactoring Scrapers to use Configs
#### [MODIFY] [src/scrapers/kabum.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/scrapers/kabum.py)
#### [MODIFY] [src/scrapers/terabyte.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/scrapers/terabyte.py)
- Refactor the `parse()` methods. Instead of hardcoded strings like `soup.find(class_="finalPrice")`, the parsers will use `soup.select_one(selectors["price_cash"])`.
- Add validation: If critical selectors (like `price_cash` or `title`) return `None`, the scraper will `raise SelectorOutdatedException`.
- Set `parser_version` to "v1" for both.

---

### 5. Engine Orchestration Updates
#### [MODIFY] [src/engine/scheduler.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/engine/scheduler.py)
- Update the `run_scraper` loop to catch `SelectorOutdatedException` explicitly and log a CRITICAL alert. This provides immediate telemetry when a store updates its layout, isolating the failure to that specific store without crashing the orchestration.

---

### 6. QA & Testing
#### [MODIFY] [tests/unit/test_parsers.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/tests/unit/test_parsers.py)
#### [MODIFY] [tests/integration/test_engine.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/tests/integration/test_engine.py)
- Update unit tests to instantiate scrapers with mock TOML configs or ensure the real TOML files match the HTML fixtures.
- Add specific unit tests to assert that a `SelectorOutdatedException` is properly raised when provided with bad HTML.

## User Review Required

> [!CAUTION]
> This change alters the database schema again by adding the `parser_version` column. Since we are using an SQLite database and the `seed_db.py` script clears and seeds the DB, we can just drop/recreate the tables. Are you okay with clearing the current SQLite database records to apply this schema upgrade?

> [!IMPORTANT]
> Is there any specific alerting mechanism (e.g., Email, Telegram, Discord) you want to trigger when a `SelectorOutdatedException` happens, or is a CRITICAL log entry sufficient for this phase?
