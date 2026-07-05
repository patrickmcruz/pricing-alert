# Walkthrough: Gitflow TOML Configuration

We have successfully migrated the application configuration from scattered hardcoded files to a centralized `.toml` file, bringing in native Python 3.11 `tomllib` support for robust environment management.

## Changes Made

1. **New `config.toml` file**: Created at the root of the project, establishing our `develop`, `staging`, and `production` environments.
   ```toml
   [develop]
   db_path = "data/prices_dev.db"
   log_level = "DEBUG"

   [staging]
   db_path = "data/prices_staging.db"
   log_level = "INFO"

   [production]
   db_path = "data/prices.db"
   log_level = "WARNING"
   ```
2. **Updated `src/core/config.py`**: Now implements the `AppSettings` class which reads `APP_ENV` (defaulting to `develop`), dynamically parses the correct section from the `.toml` file, and establishes logging levels globally.
3. **Refactored Entrypoints**: Removed manual `os.path.join` calls for DB initialization. `main.py`, `src/ui/dashboard.py`, and `scripts/seed_db.py` now uniformly import `from src.core.config import settings`.
4. **Architectural Blueprint Updated**: Added a new mandatory rule into `.agents/AGENTS.md` strictly requiring centralized Gitflow environment configuration using `APP_ENV`.

## Validation

The test suite successfully passed all checks, guaranteeing no breaking regressions in the architecture!

> [!TIP]
> Since the default `APP_ENV` is `develop`, any execution of the Streamlit dashboard or orchestrator will now use `prices_dev.db`. If you want to use the production data, run them as `APP_ENV=production python main.py` or `APP_ENV=production streamlit run src/ui/dashboard.py`.
