import os
import pytest

# Ensure the test environment is loaded before any core modules
os.environ["APP_ENV"] = "test"

@pytest.fixture(autouse=True)
def setup_test_env():
    """Ensure tests always use the test environment."""
    os.environ["APP_ENV"] = "test"
