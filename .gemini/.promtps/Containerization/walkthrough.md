# Dockerization Complete!

I have successfully containerized your GPU Pricing Alert application. The architecture has been split into two independent services that seamlessly share the necessary SQLite database file using Docker Volumes.

## What was added:

### 1. `Dockerfile.orchestrator`
This container runs `main.py` in the background. It is built using a lightweight Python 3.11 image but explicitly installs **Playwright** and its **Chromium** browser dependencies inside the container so your web scrapers can execute headlessly without needing any local browser installations.

### 2. `Dockerfile.dashboard`
This container runs the Streamlit UI (`dashboard.py`). It exposes port `8501` to your host machine so you can access the dashboard from your browser.

### 3. `docker-compose.yml`
This file stitches the two containers together:
- It automatically configures both containers to run in the `production` environment via `APP_ENV`.
- **Shared Data Volume:** It mounts your local `./data` folder directly into both containers at `/app/data`. This means the `prices.db` file, your `target-stores-list.json`, and all your CSS selectors are safely read and written, allowing the Dashboard to immediately see new prices scraped by the Orchestrator.
- **Shared Configuration:** It maps `./config.toml` so you can change global configuration settings without having to rebuild the container images.

> [!TIP]
> **How to run the application:**
> 1. Make sure Docker is running on your machine.
> 2. Open your terminal in the project root and run: `docker-compose build` (this might take a few minutes the first time to download Chromium).
> 3. Run: `docker-compose up -d`
> 4. Go to `http://localhost:8501` to view your dashboard!
