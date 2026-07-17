import os

from dotenv import load_dotenv

from src.core.config import AppSettings

def test_load_config_test_env():
    """Verify that load_config correctly picks up the [test] environment."""
    config = AppSettings("test")
    assert config.config_data["db_name"] == "pricing_test"
    assert config.log_level == "DEBUG"


def test_load_dotenv_populates_missing_env_vars(tmp_path, monkeypatch):
    """
    Regression test: config.py's module-level load_dotenv(PROJECT_ROOT/.env)
    is what makes MERCADOLIVRE_APP_ID/SECRET (and any other .env-only
    credential) available when running locally - python main.py, scripts,
    ad-hoc tests - none of which ever sourced .env before this fix. Docker
    Compose's env_file: .env directive is a separate mechanism that only
    covers the containerized path.
    """
    monkeypatch.delenv("SOME_LOCAL_ONLY_CREDENTIAL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("SOME_LOCAL_ONLY_CREDENTIAL=from-dotenv\n")

    load_dotenv(str(env_file))

    assert os.environ["SOME_LOCAL_ONLY_CREDENTIAL"] == "from-dotenv"


def test_load_dotenv_does_not_override_existing_env_vars(tmp_path, monkeypatch):
    """
    override=False (load_dotenv's default, used in config.py) means a
    variable Docker Compose's env_file already injected into the container's
    environment always wins over whatever's in a bundled .env - the fix must
    not change behavior for the already-working containerized path.
    """
    monkeypatch.setenv("SOME_SHARED_CREDENTIAL", "from-container-env")
    env_file = tmp_path / ".env"
    env_file.write_text("SOME_SHARED_CREDENTIAL=from-dotenv\n")

    load_dotenv(str(env_file))

    assert os.environ["SOME_SHARED_CREDENTIAL"] == "from-container-env"


def test_settings_reads_ml_and_telegram_credentials_from_environment(monkeypatch):
    """
    Whether a credential ends up in os.environ via Docker's env_file or via
    load_dotenv() locally, AppSettings must surface it identically - this is
    the contract the Mercado Livre scraper (and the Telegram channel) depend
    on via settings.ml_app_id/ml_secret_key/telegram_bot_token/telegram_chat_id.
    """
    monkeypatch.setenv("MERCADOLIVRE_APP_ID", "test-app-id")
    monkeypatch.setenv("MERCADOLIVRE_APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "test-chat-id")

    settings = AppSettings("test")

    assert settings.ml_app_id == "test-app-id"
    assert settings.ml_secret_key == "test-secret"
    assert settings.telegram_bot_token == "test-bot-token"
    assert settings.telegram_chat_id == "test-chat-id"
