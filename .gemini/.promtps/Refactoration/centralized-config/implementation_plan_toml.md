# TOML Configuration & Gitflow Environments Plan

Based on your request, we will centralize all hardcoded paths and configurations into a `config.toml` file using Python best practices. This will establish distinct environments (development, staging, production) to align with a Gitflow approach.

## Proposed Changes

---

### 1. Configuration File
#### [NEW] [config.toml](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/config.toml)
We will create a centralized TOML file containing the three required Gitflow environments:
- `[develop]`: Local development database (`data/prices_dev.db`), DEBUG logging.
- `[staging]`: Pre-production database (`data/prices_staging.db`), INFO logging.
- `[production]`: Live database (`data/prices.db`), WARNING logging.

---

### 2. Python Configuration Loader
#### [MODIFY] [src/core/config.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/core/config.py)
We will use Python 3.11's native `tomllib` (no external dependencies needed) to load the configuration.
- It will read the `APP_ENV` system environment variable to determine which block to load (defaults to `develop`).
- It will expose a `settings` object containing `db_path`, `log_level`, etc.

---

### 3. Refactoring Hardcoded Values
#### [MODIFY] [main.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/main.py)
#### [MODIFY] [src/ui/dashboard.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/ui/dashboard.py)
#### [MODIFY] [scripts/seed_db.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/scripts/seed_db.py)
We will remove the hardcoded `DB_PATH` values and import `settings` from `src.core.config`.

---

### 4. Updating the Blueprint
#### [MODIFY] [.agents/AGENTS.md](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/.agents/AGENTS.md)
We will add a new section documenting the centralized configuration rule, enforcing the usage of `config.toml` and Gitflow environments (`develop`, `staging`, `production`) for future AI tasks.

## User Review Required

> [!CAUTION]
> By default, `APP_ENV` will be set to `develop`, meaning the application will use `data/prices_dev.db` moving forward unless you explicitly run it with `APP_ENV=production`. 
> 
> *Do you approve this configuration schema?*
