# **ARTIFACT 1: Requirements Specification and Architecture (System Specification)**

## 1. Overview

Build a local, single-user, 100% open-source web application for automated GPU price monitoring, initially targeting the **GeForce RTX 5070** and **GeForce RTX 5070 Ti**.

The application must execute scheduled scraping jobs, collect product and pricing information from multiple Brazilian e-commerce stores, normalize the extracted data, and persist the historical results in a local database for analysis through a web dashboard.

The architecture must be modular, extensible, asynchronous, and designed to allow new stores to be added with minimal code changes.

---

## 2. Mandatory Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| Dashboard | Streamlit |
| Database | SQLite3 |
| Data Validation | Pydantic v2 |
| Scheduler | APScheduler (`AsyncIOScheduler`) |
| HTTP Client | HTTPX (HTTP/2 enabled) |
| Browser Automation | Playwright (async) + playwright-stealth |
| Async Runtime | asyncio |
| Packaging | pip + requirements.txt |
| Containerization | Docker (optional, but supported) |

---

## 3. Target Stores

The list of supported stores **must** be stored as a JSON object located at:

```
./data/target-stores-list.json
```

Each entry must contain the standardized store name and its official base URL.

---

## 4. Functional Requirements

The system must:

- Monitor products using one or more user-defined search keywords.
- Support multiple scheduled execution times per store.
- Scrape all configured stores asynchronously.
- Normalize all extracted data into a common data model.
- Persist every execution into the local database.
- Preserve historical pricing information.
- Provide a Streamlit dashboard for configuration and historical analysis.
- Continue execution even if one or more scrapers fail.

---

## 5. Non-Functional Requirements

The application must:

- Be fully asynchronous whenever network I/O is involved.
- Execute entirely on the local machine.
- Require no external APIs or paid services.
- Be compatible with Windows, Linux, and macOS.
- Be easily extensible through modular scraper implementations.
- Use only open-source libraries.

---

## 6. Extraction Strategy

The agent must determine the appropriate extraction engine for each store:

- **HTTPX** for stores that allow direct HTTP requests.
- **Playwright + playwright-stealth** for stores protected by WAFs, Cloudflare, or aggressive anti-bot mechanisms.

All extraction implementations must inherit from the common `BaseScraper` abstraction.

---

## 7. Architecture Principles

The implementation must follow:

- Strategy Pattern for scraper implementations.
- Single Responsibility Principle (SRP).
- Dependency Inversion where appropriate.
- Separation of concerns between extraction, orchestration, persistence, shared utilities, and presentation.
- Asynchronous programming using `asyncio`.
- Strong typing throughout the project.

---

## 8. Implementation Requirements

The agent must ensure that:

- The project remains fully modular and extensible.
- Every scraper is implemented as an independent strategy.
- Shared code is never duplicated across scraper implementations.
- All extracted data is validated through Pydantic before persistence.
- Every scheduled execution is isolated so that failures do not interrupt other jobs.
- Logging is implemented consistently across all layers.
- Configuration is centralized and reusable.
- New stores can be added without modifying the orchestration engine.
- The implementation follows the project directory structure defined in **Artifact 2**.
- The application is production-ready, fully type-annotated, and compatible with Python 3.11+.

## 9. Testability Requirements

The system must be designed to maximize deterministic automated testing.

All business logic must be independently testable without requiring:

- Internet connectivity
- Browser automation
- SQLite
- APScheduler
- Streamlit

Network access, browser automation, scheduling, and persistence must be isolated behind abstractions that can be replaced with mocks during testing.