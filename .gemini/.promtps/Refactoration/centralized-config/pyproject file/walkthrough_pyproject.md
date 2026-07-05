# Walkthrough: Consolidating to `pyproject.toml`

We have successfully modernized the Python project configuration by migrating scattered dependency and tooling files into a single, unified `pyproject.toml` file!

## What We Achieved

1. **Created `pyproject.toml`**: 
   - Centralized project metadata (name, description).
   - Moved production dependencies from `requirements.txt`.
   - Moved development dependencies from `requirements-dev.txt` into an `optional-dependencies` block.
   - Merged `[pytest]` rules from `pytest.ini`.
   - Merged `[mypy]` rules from `mypy.ini`.

2. **Cleaned the Root Directory**:
   - Permanently deleted `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, and `mypy.ini`. The project structure is incredibly clean now.

3. **Validation**:
   - Pytest was able to automatically pick up `pyproject.toml` as its configuration file and ran correctly.
   - MyPy successfully ran without missing import errors using the settings defined in `pyproject.toml`.

4. **Updated Blueprint**:
   - `AGENTS.md` now strictly enforces that all future dependencies and configurations must be placed in `pyproject.toml`.

## How to use `pyproject.toml`

In modern workflows, instead of running `pip install -r requirements.txt`, you will install your project in editable mode directly:

- **Install for Production:**
  ```bash
  pip install -e .
  ```
- **Install for Development:**
  ```bash
  pip install -e .[dev]
  ```
