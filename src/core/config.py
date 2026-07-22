import os
import tomllib
import logging
from typing import Any, Dict

from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Docker Compose injects .env into the container via env_file, so os.environ
# already has these variables there - but running locally (python main.py,
# scripts, tests) never sources .env on its own. load_dotenv() fills that gap;
# override=False (its default) means any variable Docker/the shell already
# set wins, so this changes nothing for the containerized path.
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

class AppSettings:
    """Global configuration parsed from config.toml based on APP_ENV."""
    
    def __init__(self, env: str = "develop"):
        self.env = env
        self.config_path = os.path.join(PROJECT_ROOT, "config.toml")
        self.config_data = self._load_config()
        
        # PostgreSQL connection. Host/port/name/user are non-secret and live in
        # config.toml per-environment; the password is always an env var
        # (never committed), same pattern as the scraper/alert credentials below.
        self.db_host = self.config_data.get("db_host", "localhost")
        self.db_port = self.config_data.get("db_port", 5432)
        self.db_name = self.config_data.get("db_name", "pricing")
        self.db_user = self.config_data.get("db_user", "pricing")
        self.db_password = os.getenv("POSTGRES_PASSWORD", "pricing")
        self.db_dsn = (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

        self.log_level = self.config_data.get("log_level", "INFO")
        self.default_manufacturer = self.config_data.get("default_manufacturer", "NVIDIA")
        self.default_gpus = self.config_data.get("default_gpus", [])
        self.default_stores = self.config_data.get("default_stores", [])
        self.default_brands = self.config_data.get("default_brands", [])
        self.max_skus_per_chipset = self.config_data.get("max_skus_per_chipset", 0)
        
        self.headless = self.config_data.get("headless", True)

        # Hard ceiling on a single SKU's fetch+parse (src/engine/scheduler.py
        # wraps scraper.execute() in asyncio.wait_for with this) - guarantees
        # one hung page (network stall, dead browser process, anti-bot loop)
        # can't block an entire store's run indefinitely.
        self.scraper_timeout_seconds = self.config_data.get("scraper_timeout_seconds", 120)

        # Timezone used for cron scheduling (main.py, PriceEngine), the daily
        # backup job, Playwright's context locale/tz spoofing, and every
        # timestamp displayed in logs/the dashboard - single source of truth
        # instead of "America/Sao_Paulo" duplicated across half a dozen files.
        self.display_timezone = self.config_data.get("display_timezone", "America/Sao_Paulo")

        # Applied to every store loaded from stores_config_path unless/until
        # per-store cron overrides exist.
        self.default_cron_times = self.config_data.get(
            "default_cron_times", ["08:00", "12:00", "16:00", "20:00"]
        )

        # Playwright navigation/action timeouts (ms). Terabyte gets its own,
        # longer value - its fetch() also runs simulate_human_interaction()
        # before capturing the HTML, and its anti-bot challenge can be slower
        # to clear than Kabum's - not arbitrary drift.
        self.navigation_timeout_ms = self.config_data.get("navigation_timeout_ms", 30000)
        self.terabyte_navigation_timeout_ms = self.config_data.get(
            "terabyte_navigation_timeout_ms", 45000
        )

        # httpx AsyncClient timeout (seconds) for REST-based scrapers (Mercado Livre).
        self.http_timeout_seconds = self.config_data.get("http_timeout_seconds", 30.0)

        # Store registry and legacy discovery manifest paths - resolved against
        # PROJECT_ROOT so they don't depend on the process's working directory.
        self.stores_config_path = os.path.join(
            PROJECT_ROOT, self.config_data.get("stores_config_path", "data/target-stores-list.json")
        )
        self.target_urls_path = os.path.join(
            PROJECT_ROOT, self.config_data.get("target_urls_path", "data/target_urls.json")
        )

        # Plain-text log file (see src/core/logging_setup.py:configure_logging).
        self.log_file_path = os.path.join(
            PROJECT_ROOT, self.config_data.get("log_file_path", "data/orchestrator.log")
        )

        # How many timestamped snapshots scripts/backup_db.py keeps before
        # pruning, and what time of day main.py schedules the daily one.
        self.backup_retention_count = self.config_data.get("backup_retention_count", 30)
        self.backup_cron_hour = self.config_data.get("backup_cron_hour", 3)
        self.backup_cron_minute = self.config_data.get("backup_cron_minute", 0)

        # How often TriggerProcessor polls for "run now" dashboard requests.
        self.trigger_poll_interval_seconds = self.config_data.get(
            "trigger_poll_interval_seconds", 5.0
        )

        # Mercado Livre API Credentials (loaded from ENV natively, or config.toml as fallback)
        self.ml_app_id = os.getenv("MERCADOLIVRE_APP_ID", self.config_data.get("MERCADOLIVRE_APP_ID"))
        self.ml_secret_key = os.getenv("MERCADOLIVRE_APP_SECRET_KEY", os.getenv("MERCADOLIVRE_APP_SECRET", self.config_data.get("MERCADOLIVRE_APP_SECRET")))

        # Telegram alert channel credentials (loaded from ENV natively, or config.toml as fallback)
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", self.config_data.get("TELEGRAM_BOT_TOKEN"))
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", self.config_data.get("TELEGRAM_CHAT_ID"))

        # Amazon Selling Partner API (SP-API) credentials (loaded from ENV natively, or
        # config.toml as fallback). Unlike Mercado Livre's client_credentials grant, SP-API
        # exchanges a long-lived, per-seller refresh_token (obtained once via self-authorization
        # in Seller Central) for short-lived access tokens - see src/scrapers/amazon.py.
        self.amazon_lwa_client_id = os.getenv(
            "AMAZON_LWA_APP_CLIENT_ID", self.config_data.get("AMAZON_LWA_APP_CLIENT_ID")
        )
        self.amazon_lwa_client_secret = os.getenv(
            "AMAZON_LWA_APP_CLIENT_SECRET_KEY", self.config_data.get("AMAZON_LWA_APP_CLIENT_SECRET_KEY")
        )
        self.amazon_sp_api_refresh_token = os.getenv(
            "AMAZON_SP_API_REFRESH_TOKEN", self.config_data.get("AMAZON_SP_API_REFRESH_TOKEN")
        )

        # Sandbox mode: the SP-API sandbox lives on its own host and only accepts a refresh
        # token minted from Seller Central's "Teste de sandbox" page (production refresh tokens
        # don't work there, and vice versa). It returns static mock data, not real Amazon.com.br
        # prices - useful only to verify the auth/request wiring before production access exists.
        self.amazon_spapi_sandbox = os.getenv(
            "AMAZON_SPAPI_SANDBOX", str(self.config_data.get("amazon_spapi_sandbox", False))
        ).strip().lower() in ("1", "true", "yes")
        self.amazon_sp_api_sandbox_refresh_token = os.getenv(
            "AMAZON_SP_API_SANDBOX_REFRESH_TOKEN", self.config_data.get("AMAZON_SP_API_SANDBOX_REFRESH_TOKEN")
        )

        # NA region endpoint covers amazon.com.br; A2Q3Y263D00KWC is the fixed
        # marketplaceId Amazon assigns to the Brazil marketplace.
        self.amazon_spapi_base_url = self.config_data.get(
            "amazon_spapi_base_url", "https://sellingpartnerapi-na.amazon.com"
        )
        self.amazon_spapi_sandbox_base_url = self.config_data.get(
            "amazon_spapi_sandbox_base_url", "https://sandbox.sellingpartnerapi-na.amazon.com"
        )
        self.amazon_marketplace_id = self.config_data.get("amazon_marketplace_id", "A2Q3Y263D00KWC")

    def _load_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            logging.warning("config.toml not found. Falling back to defaults.")
            return {}
            
        with open(self.config_path, "rb") as f:
            full_config = tomllib.load(f)
            
        if self.env not in full_config:
            logging.warning("Environment '%s' not found in config.toml. Falling back to 'develop'.", self.env)
            return full_config.get("develop", {})
            
        return full_config[self.env]

# Determine the environment from OS variables (defaults to develop)
app_env = os.getenv("APP_ENV", "develop")
settings = AppSettings(app_env)
