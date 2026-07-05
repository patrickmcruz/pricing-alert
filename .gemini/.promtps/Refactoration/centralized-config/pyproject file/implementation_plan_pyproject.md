# Implementation Plan: Migrate to `pyproject.toml`

Based on modern Python best practices (PEP 621), we will consolidate all fragmented dependency and tool configuration files into a single `pyproject.toml` at the root of the project.

## Proposed Changes

---

### 1. Unified Project Configuration
#### [NEW] [pyproject.toml](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/pyproject.toml)
We will create a standard `pyproject.toml` file that defines:
- **Project Metadata**: Name, version, description, and Python version requirement (`>=3.11`).
- **Dependencies**: All packages currently listed in `requirements.txt` (e.g., `streamlit`, `pydantic`, `httpx[http2]`, etc.).
- **Dev Dependencies**: All packages currently in `requirements-dev.txt` using the `[project.optional-dependencies]` section.
- **Tool Configurations**:
  - `[tool.pytest.ini_options]`: Contains the settings from `pytest.ini` (`pythonpath = .`, `asyncio_mode = "auto"`).
  - `[tool.mypy]`: Contains settings from `mypy.ini` (`explicit_package_bases`, `ignore_missing_imports`, etc.).

---

### 2. Cleanup Fragmented Files
#### [DELETE] [requirements.txt](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/requirements.txt)
#### [DELETE] [requirements-dev.txt](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/requirements-dev.txt)
#### [DELETE] [pytest.ini](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/pytest.ini)
#### [DELETE] [mypy.ini](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/mypy.ini)
We will permanently remove these files, ensuring there is a single source of truth for the project.

---

### 3. Blueprint Documentation
#### [MODIFY] [.agents/AGENTS.md](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/.agents/AGENTS.md)
We will update the architecture blueprint to document that Python packages and linter/testing configurations must be managed exclusively through `pyproject.toml`.

## Verification Plan
1. Delete the old config files and write the new `pyproject.toml`.
2. Run `pytest` to ensure it still automatically discovers `asyncio` and the `pythonpath` correctly from the new TOML file.
3. Run `mypy src tests scripts` to ensure static typing ignores missing imports and runs without error.

## User Review Required

> [!NOTE]
> Moving to `pyproject.toml` means you will install dependencies in the future using `pip install -e .` (to install the app and core dependencies) and `pip install -e .[dev]` (to install development tools like pytest/mypy).
> 
> Are you ready to proceed with this cleanup?
