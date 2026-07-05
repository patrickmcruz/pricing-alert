# Phase 5: Streamlit UI & Entrypoint Implementation Plan

This plan details the steps to build the presentation layer and the application bootstrap script for the GPU Price Tracker, bridging the orchestrator and the database.

## Proposed Changes

---

### Dependency Updates

#### [MODIFY] [requirements.txt](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/requirements.txt)
To build a beautiful and functional Streamlit dashboard, we need data manipulation and charting libraries.
- **Action**: Append `pandas` (for dataframe management) and `plotly` (for interactive line charts) to the requirements.

---

### Streamlit Dashboard

#### [NEW] [src/ui/dashboard.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/ui/dashboard.py)
We will implement the user interface using Streamlit.
- It will read the `prices` table from our SQLite database (using `pandas.read_sql`).
- It will feature a sidebar to filter by `search_keyword` (e.g., RTX 5070 vs RTX 5070 Ti) and `store_name`.
- It will display KPI metrics (Lowest Price Available).
- It will render an interactive Plotly line chart showing historical price trends over time.
- It will display the raw data in a sortable grid.

---

### Application Entrypoint

#### [NEW] [main.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/main.py)
We will create the main entry point to run the background orchestrator.
- It will define an `async main()` function.
- It will initialize the `SQLitePriceRepository` and ensure the schema is created.
- It will load the target stores from `data/target-stores-list.json`.
- It will instantiate the `PriceEngine` with `AsyncIOScheduler`.
- It will register `KabumScraper` and `TerabyteScraper`.
- It will define the `StoreConfig` for each store (e.g., target keywords: "rtx 5070", "rtx 5070 ti") and build the schedule.
- It will start the scheduler and block the main thread to keep the engine alive.

## User Review Required

> [!IMPORTANT]
> The Streamlit dashboard relies heavily on `pandas` and `plotly` for standard data visualization. I propose adding them to our dependencies.
> Additionally, `main.py` will act exclusively as the orchestrator runner, while the UI will be launched independently via `streamlit run src/ui/dashboard.py`.
> 
> *Do you approve this Phase 5 implementation plan and the dependency additions?*

## Verification Plan

### Automated Tests
- We will not run automated tests for the UI components in this phase as per standard Streamlit practices, but the logic in `main.py` heavily relies on the tested abstractions from Phases 1-4.

### Manual Verification
- We will ensure `main.py` can be executed without crashing.
- We will ensure `dashboard.py` loads successfully (though it will show an empty database initially).
