import pytest
import os
import json
from unittest.mock import patch, mock_open
from src.core.i18n import I18n

@pytest.fixture(autouse=True)
def reset_i18n_singleton():
    """Ensure the singleton is reset between tests to avoid state bleed."""
    I18n._instance = None
    yield
    I18n._instance = None

@pytest.fixture
def mock_filesystem():
    """Mock os.path, os.listdir, and open to return virtual JSON data."""
    pt_br_data = {
        "greeting": "Olá",
        "welcome": "Bem-vindo, {name}!",
        "only_in_pt": "Apenas em português"
    }
    
    en_us_data = {
        "greeting": "Hello",
        "welcome": "Welcome, {name}!"
    }

    # Custom mock for builtins.open to return different data based on filename
    def custom_mock_open(filename, *args, **kwargs):
        if "pt_BR.json" in str(filename):
            return mock_open(read_data=json.dumps(pt_br_data))()
        elif "en_US.json" in str(filename):
            return mock_open(read_data=json.dumps(en_us_data))()
        return mock_open(read_data="{}")()

    with patch("os.path.exists", return_value=True), \
         patch("os.listdir", return_value=["pt_BR.json", "en_US.json"]), \
         patch("builtins.open", new_callable=lambda: custom_mock_open):
        yield

def test_singleton_pattern():
    """Verify that I18n is a singleton."""
    i1 = I18n()
    i2 = I18n()
    assert i1 is i2

def test_load_locales(mock_filesystem):
    """Test that locales are loaded correctly from mocked disk."""
    i18n = I18n()
    
    assert "pt_BR" in i18n.locales
    assert "en_US" in i18n.locales
    assert i18n.locales["pt_BR"]["greeting"] == "Olá"
    assert i18n.locales["en_US"]["greeting"] == "Hello"

def test_translation_default_lang(mock_filesystem):
    """Test translation using the default language (pt_BR)."""
    i18n = I18n()
    
    assert i18n.t("greeting") == "Olá"
    assert i18n.t("greeting", lang="pt_BR") == "Olá"
    assert i18n.t("greeting", lang="pt-BR") == "Olá" # tests the pt-BR UI fallback

def test_translation_other_lang(mock_filesystem):
    """Test translation using a non-default language."""
    i18n = I18n()
    
    assert i18n.t("greeting", lang="en_US") == "Hello"
    assert i18n.t("greeting", lang="en-US") == "Hello" # tests the en-US UI fallback

def test_translation_fallback_to_pt_br(mock_filesystem):
    """Test fallback to pt_BR if a key is missing in the target language."""
    i18n = I18n()
    
    # only_in_pt is not in en_US.json, so it should fall back to pt_BR
    assert i18n.t("only_in_pt", lang="en_US") == "Apenas em português"

def test_translation_fallback_to_key(mock_filesystem):
    """Test fallback to the raw key if it doesn't exist in any loaded locale."""
    i18n = I18n()
    
    assert i18n.t("missing_key") == "missing_key"
    assert i18n.t("missing_key", lang="en_US") == "missing_key"

def test_translation_with_kwargs(mock_filesystem):
    """Test string formatting using kwargs."""
    i18n = I18n()
    
    assert i18n.t("welcome", name="Eduardo") == "Bem-vindo, Eduardo!"
    assert i18n.t("welcome", lang="en_US", name="Eduardo") == "Welcome, Eduardo!"

def test_translation_with_missing_kwargs(mock_filesystem):
    """Test safe handling when kwargs are expected but not provided."""
    i18n = I18n()
    
    # Should not crash, just return the raw string with unformatted brace
    assert i18n.t("welcome") == "Bem-vindo, {name}!"
