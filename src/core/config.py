import os
import tomllib
import logging
from typing import Any, Dict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

class AppSettings:
    """Global configuration parsed from config.toml based on APP_ENV."""
    
    def __init__(self, env: str = "develop"):
        self.env = env
        self.config_path = os.path.join(PROJECT_ROOT, "config.toml")
        self.config_data = self._load_config()
        
        # Ensure DB paths are resolved relative to project root
        raw_db_path = self.config_data.get("db_path", "data/prices_dev.db")
        self.db_path = os.path.join(PROJECT_ROOT, raw_db_path)
        
        self.log_level = self.config_data.get("log_level", "INFO")
        self.default_manufacturer = self.config_data.get("default_manufacturer", "NVIDIA")
        self.default_gpus = self.config_data.get("default_gpus", [])
        self.default_stores = self.config_data.get("default_stores", [])
        self.default_brands = self.config_data.get("default_brands", [])
        
        self.headless = self.config_data.get("headless", True)

        # Hard ceiling on a single SKU's fetch+parse (src/engine/scheduler.py
        # wraps scraper.execute() in asyncio.wait_for with this) - guarantees
        # one hung page (network stall, dead browser process, anti-bot loop)
        # can't block an entire store's run indefinitely.
        self.scraper_timeout_seconds = self.config_data.get("scraper_timeout_seconds", 120)
        
        # Mercado Livre API Credentials (loaded from ENV natively, or config.toml as fallback)
        self.ml_app_id = os.getenv("MERCADOLIVRE_APP_ID", self.config_data.get("MERCADOLIVRE_APP_ID"))
        self.ml_secret_key = os.getenv("MERCADOLIVRE_APP_SECRET_KEY", os.getenv("MERCADOLIVRE_APP_SECRET", self.config_data.get("MERCADOLIVRE_APP_SECRET")))

        # Telegram alert channel credentials (loaded from ENV natively, or config.toml as fallback)
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", self.config_data.get("TELEGRAM_BOT_TOKEN"))
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", self.config_data.get("TELEGRAM_CHAT_ID"))

        self._configure_logging()
        
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
        
    def _configure_logging(self) -> None:
        numeric_level = getattr(logging, self.log_level.upper(), logging.INFO)
        logging.basicConfig(level=numeric_level)

# Determine the environment from OS variables (defaults to develop)
app_env = os.getenv("APP_ENV", "develop")
settings = AppSettings(app_env)
