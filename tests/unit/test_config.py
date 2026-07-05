import os
from src.core.config import AppSettings

def test_load_config_test_env():
    """Verify that load_config correctly picks up the [test] environment."""
    config = AppSettings("test")
    assert config.config_data["db_path"] == ":memory:"
    assert config.log_level == "DEBUG"
