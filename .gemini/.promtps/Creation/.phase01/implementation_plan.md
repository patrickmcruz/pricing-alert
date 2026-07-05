# Phase 1: Foundation & Core Abstractions Implementation Plan

This plan details the exact steps and files to be created to fulfill Phase 1 of the GPU Price Tracker architecture, as dictated by `AGENTS.md` and Artifacts 1-6.

## Proposed Changes

---

### Project Structure & Dependencies

We will initialize the core project structure and define the required packages.

#### [NEW] [requirements.txt](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/requirements.txt)
Will contain production dependencies: `streamlit`, `pydantic`, `apscheduler`, `httpx[http2]`, `playwright`, `playwright-stealth`.

#### [NEW] [requirements-dev.txt](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/requirements-dev.txt)
Will contain development dependencies: `pytest`, `pytest-asyncio`, `pytest-mock`, `respx`, `pytest-cov`, `mypy`, `ruff`, `black`.

#### [NEW] Directory Structure
Will create the necessary directories: `src/core`, `src/scrapers`, `src/engine`, `src/repositories`, `src/ui`, `data`, and `tests/` with its subdirectories.

---

### Core Data Contracts

#### [NEW] [src/core/contract.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/core/contract.py)
Will implement the `PriceContract` and `StoreConfig` Pydantic models as exactly specified in Artifact 3. These models enforce strict validation, immutability (`frozen=True`), and proper types (`Decimal`, timezone-aware UTC `datetime`).

---

### Core Architecture Abstractions

#### [NEW] [src/core/base_scraper.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/core/base_scraper.py)
Will implement the abstract `BaseScraper` class exactly as specified in Artifact 4, enforcing the strict separation of `fetch()` (network I/O) and `parse()` (deterministic extraction logic).

#### [NEW] [src/core/http_client.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/core/http_client.py)
Will implement an initial factory for creating and managing `httpx.AsyncClient` instances.

#### [NEW] [src/core/browser.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/core/browser.py)
Will implement an initial factory for managing `Playwright` async browser contexts with `playwright-stealth`.

#### [NEW] [src/core/config.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/core/config.py)
Will implement application-level configuration management.

#### [NEW] [src/core/utils.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/core/utils.py)
Will be created as an empty utility module for future shared helper functions.

---

### Configuration Data

#### [NEW] [data/target-stores-list.json](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/data/target-stores-list.json)
Will initialize the target stores configuration with placeholder entries for Kabum and Terabyte as examples.

## User Review Required

> [!IMPORTANT]
> Please review this plan. Once you approve, I will automatically write all the code and create the files outlined above.

## Verification Plan

### Automated Tests
- No automated tests will be run yet, as Phase 1 only sets up abstractions and contracts. Testing will be integrated as concrete components are implemented.

### Manual Verification
- Verify that the generated file structure perfectly matches Artifact 2.
- Verify that `requirements.txt` and `requirements-dev.txt` have the correct packages.
