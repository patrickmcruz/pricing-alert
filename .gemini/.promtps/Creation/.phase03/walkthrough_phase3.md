# Phase 3 Walkthrough: Scrapers & HTML Fixtures (TDD)

Phase 3 is complete! We have successfully established our first store strategies and proven our deterministic parsing architecture.

## What Was Completed

### 1. HTML Parsing Support
- [MODIFY] [requirements.txt](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/requirements.txt): Added `beautifulsoup4` and `lxml` for robust, high-performance HTML parsing.

### 2. Static HTML Fixtures
- [NEW] [tests/fixtures/kabum_mock.html](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/tests/fixtures/kabum_mock.html): Created a structural mock representing Kabum's search results.
- [NEW] [tests/fixtures/terabyte_mock.html](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/tests/fixtures/terabyte_mock.html): Created a structural mock representing Terabyteshop's search results.
- These fixtures allow us to run tests indefinitely without making real HTTP requests.

### 3. Concrete Scraper Implementations
- [NEW] [src/scrapers/kabum.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/scrapers/kabum.py): Implemented `KabumScraper` adhering to the `BaseScraper` contract. Its `parse()` method efficiently extracts data using BeautifulSoup.
- [NEW] [src/scrapers/terabyte.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/scrapers/terabyte.py): Implemented `TerabyteScraper` following the exact same pattern, tailored to Terabyte's unique HTML selectors.
- Both scrapers use a robust `_clean_price()` helper to safely transform BRL strings into `Decimal` objects to prevent floating point issues.

### 4. Deterministic Unit Tests
- [NEW] [tests/unit/test_parsers.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/tests/unit/test_parsers.py): Created the unit tests to validate our TDD strategy.
  - The tests load the static HTML fixtures directly from the filesystem.
  - They execute the `parse()` methods in full isolation.
  - They assert that all values (prices, titles, UUID generation) match the required `PriceContract` schema.

---

## Next Steps

With the scrapers correctly parsing data, we have reached **Phase 4: Orchestration & Scheduling Engine**! 

In Phase 4, we will implement the `PriceEngine` using `apscheduler` to dynamically manage the execution of these newly minted scraper strategies, injecting the HTTP clients and the SQLite repository!

Let me know whenever you're ready to proceed to Phase 4!
