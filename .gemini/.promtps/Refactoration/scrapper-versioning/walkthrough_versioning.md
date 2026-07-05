# Walkthrough: Config-Driven Scraper Versioning

We have successfully overhauled our scraper parsing engine to be resilient, versioned, and entirely configuration-driven!

## Changes Made

1. **Selector Extraction**:
   - Removed all hardcoded CSS class names from `src/scrapers/kabum.py` and `src/scrapers/terabyte.py`.
   - Extracted these DOM paths into dedicated TOML configuration files: `data/selectors/kabum.toml` and `data/selectors/terabyte.toml`.
   - If a store updates its layout, we simply create a `[v2]` block in the TOML file rather than touching the Python logic.

2. **Database Traceability**:
   - Added `parser_version` to the `PriceContract` schema.
   - Re-initialized the `prices` SQLite table to store this field. Now every single extracted price retains a record of exactly *which* parser version scraped it (e.g., `kabum_v1`). 

3. **Resilient Orchestration (`SelectorOutdatedException`)**:
   - Added `SelectorOutdatedException` to `BaseScraper`. 
   - If a scraper cannot find critical UI components like the price or the title (indicating the store likely deployed a new UI), it raises this specific exception.
   - The Orchestrator (`PriceEngine`) explicitly catches this, safely skips the failed URL, and logs a **CRITICAL** error alerting you to the UI change without crashing the rest of the batch!

## Validation

The test suite successfully passed all checks. The static type checks (MyPy) verified that our new `parser_version` contracts are flawlessly integrated across the repository.

```text
Success: no issues found in 29 source files
============================= test session starts =============================
collected 6 items

tests\integration\test_engine.py ..                                      [ 33%]
tests\unit\test_parsers.py ..                                            [ 66%]
tests\unit\test_spiders.py ..                                            [100%]

============================== 6 passed in 0.40s ==============================
```
