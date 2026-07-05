# **ARTIFACT 2: Project Directory Structure**

The project **must** strictly adhere to the directory structure below. All shared architecture components, abstract base classes, data contracts, configuration, and reusable utilities **must** reside exclusively within the `src/core` package to maintain a single source of truth and prevent duplicate or competing implementations.

```plaintext
/gpu-price-tracker
├── /src
│
│   ├── /core                         # Shared architecture and abstractions
│   │   ├── __init__.py
│   │   ├── contract.py               # Pydantic data models
│   │   ├── base_scraper.py           # Abstract Base Class
│   │   ├── config.py                 # Application configuration
│   │   ├── browser.py                # Playwright factory
│   │   ├── http_client.py            # HTTPX client factory
│   │   └── utils.py                  # Shared helper functions
│   │
│   ├── /scrapers                     # One scraper per store
│   │   ├── __init__.py
│   │   ├── kabum.py
│   │   ├── terabyte.py
│   │   └── ...
│   │
│   ├── /engine                       # Application orchestration
│   │   ├── __init__.py
│   │   └── scheduler.py
│   │
│   ├── /repositories                 # Persistence layer
│   │   ├── __init__.py
│   │   ├── base_repository.py
│   │   └── sqlite_repository.py
│   │
│   ├── /ui                           # Streamlit application
│   │   ├── __init__.py
│   │   └── dashboard.py
│   │
│   └── /data
│       └── target-stores-list.json
│
├── /tests
│   ├── /fixtures
│   ├── /unit
│   ├── /integration
│   └── /e2e
│
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── docker-compose.yml
├── Dockerfile
└── main.py
```

---

## **Implementation Requirements**

The agent must ensure that:

- The project structure matches this directory layout exactly.
- All shared abstractions, contracts, configuration, and reusable utilities reside exclusively within `src/core`.
- Every scraper is implemented as an independent strategy inside `src/scrapers`.
- Every scraper inherits from `BaseScraper`.
- Scrapers contain only extraction logic and must not implement scheduling, persistence, or UI functionality.
- The scheduler is responsible only for orchestration and dependency injection.
- Database operations are isolated behind the Repository Pattern.
- No scraper interacts directly with SQLite or any persistence implementation.
- HTTP clients and Playwright browser contexts are created by reusable factories and injected into scrapers.
- Network resources must never be instantiated directly inside scraper implementations.
- All components must be designed for dependency injection to maximize testability.
- The architecture must support deterministic unit tests without requiring network access, browser automation, or a database.
- Static HTML fixtures must be sufficient to validate all parsing logic.
- Integration tests must replace HTTP clients, browser contexts, and repositories with mocks or stubs.
- New stores can be added by creating a single scraper module without modifying the scheduler or persistence layer.
- The architecture must follow the Strategy Pattern, Repository Pattern, Dependency Injection, and the Single Responsibility Principle (SRP).
- Shared functionality must never be duplicated outside the `src/core` package.
- All modules must be fully type-annotated and compatible with Python 3.11+.