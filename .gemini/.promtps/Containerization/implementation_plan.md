# Docker Containerization Plan

The goal is to containerize the application to ensure it can run independently of the local environment. Based on the system architecture, the application is divided into two distinct services:
1. **Orchestrator**: The backend process (`main.py`) that runs Playwright, executes spiders/scrapers, and populates the database.
2. **Dashboard**: The frontend application (`src/ui/dashboard.py`) powered by Streamlit that reads from the database.

> [!NOTE]
> Since we use an SQLite database (`data/prices.db`), both containers must share access to the `data/` directory. We will solve this by mounting a shared bind mount volume to `./data`, allowing both containers to read and write to the same database file and access the `locales` and `selectors`.

## Open Questions

> [!WARNING]
> You requested to put the database in a **separate container**. However, our strict architectural blueprint (`AGENTS.md`) mandates the use of **SQLite3**, which is a serverless, embedded database (it exists purely as a file and does not run as a standalone background service like Postgres or MySQL).
> 
> How would you like to proceed?
> **Option A (Stick to SQLite):** We don't create a separate database container. Instead, we use a dedicated Docker Volume (`pricing_db_data`) shared between the Orchestrator and Dashboard to persist the `.db` file.
> **Option B (Migrate to PostgreSQL):** I will add a `postgres:15` container to our `docker-compose.yml`, write a new `PostgresRepository` class (leveraging our Repository Pattern), and override the `AGENTS.md` rule.

## Proposed Changes

### Dockerfiles

We will create two separate Dockerfiles to keep images optimized for their specific tasks.

#### [NEW] [Dockerfile.orchestrator](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/Dockerfile.orchestrator)
This image requires Playwright and its browser binaries.
- Base: `python:3.11-slim`
- Install system dependencies required for Playwright.
- Install Python dependencies from `pyproject.toml`.
- Run `playwright install --with-deps chromium`.
- Entrypoint: `python main.py`

#### [NEW] [Dockerfile.dashboard](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/Dockerfile.dashboard)
This is a lightweight image for Streamlit.
- Base: `python:3.11-slim`
- Install Python dependencies.
- Expose port `8501`.
- Entrypoint: `streamlit run src/ui/dashboard.py --server.address=0.0.0.0`

### Docker Compose

#### [NEW] [docker-compose.yml](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/docker-compose.yml)
We will orchestrate the two services using Docker Compose.
- **Service 1:** `orchestrator`
- **Service 2:** `dashboard` (maps port 8501 to host)
- **Volumes:** 
  - `./data:/app/data` (Shares SQLite database, selectors, and i18n locales)
  - `./config.toml:/app/config.toml` (Injects configuration)
- **Environment:**
  - `APP_ENV=production` (Sets the environment to production to use `prices.db`)
  - `PYTHONUNBUFFERED=1` (Ensures logs are printed in real-time)

## User Review Required

> [!IMPORTANT]
> The Orchestrator container requires downloading Chromium binaries (~150MB). Are you okay with this slight image bloat, or would you prefer we explore a remote browser API (like browserless.io) in the future? For this iteration, bundling Chromium in the container is the standard approach.

> [!TIP]
> The `data/` directory is mapped via a local bind mount (`./data`). This means any scraping data stored in the Docker database will physically appear in your local `data/prices.db` file, and you can edit `target-stores-list.json` locally and have it immediately available in the container.

## Verification Plan
1. Run `docker-compose build`.
2. Run `docker-compose up -d`.
3. Verify the Orchestrator starts successfully and begins scraping.
4. Open `http://localhost:8501` to verify the dashboard is running and querying the shared SQLite database.
