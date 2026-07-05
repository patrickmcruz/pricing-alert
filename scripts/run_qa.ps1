Write-Host "Setting up Python Virtual Environment..."
python -m venv venv
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Activating venv and installing dependencies..."
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Running Black Formatting..."
black src tests main.py

Write-Host "Running Ruff Linting..."
ruff check src tests main.py --fix

Write-Host "Running MyPy Type Checking..."
mypy src tests main.py --ignore-missing-imports

Write-Host "Running Pytest..."
pytest tests

Write-Host "QA Gates Execution Finished!"
