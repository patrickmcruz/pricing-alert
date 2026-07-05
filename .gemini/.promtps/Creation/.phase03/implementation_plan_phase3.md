# Phase 3: Scrapers & HTML Fixtures (TDD) Implementation Plan

This plan details the steps to build the concrete scraper strategies and their corresponding unit tests for the GPU Price Tracker, adhering to the Test-Driven Development (TDD) and BaseScraper constraints specified in Artifacts 4 and 6.

## Proposed Changes

---

### Dependency Updates

#### [MODIFY] [requirements.txt](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/requirements.txt)
To parse HTML efficiently within our `parse()` methods, we need an HTML parsing library. I propose using the industry standard `beautifulsoup4` paired with the fast `lxml` parser.
- **Action**: Append `beautifulsoup4` and `lxml` to the production requirements.

---

### Static HTML Fixtures

#### [NEW] [tests/fixtures/kabum_mock.html](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/tests/fixtures/kabum_mock.html)
#### [NEW] [tests/fixtures/terabyte_mock.html](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/tests/fixtures/terabyte_mock.html)
We will create mock HTML files that simulate the basic DOM structure of a product search result page for Kabum and Terabyte. This fulfills the requirement to decouple parsing from network I/O, allowing us to unit test the parsers completely offline. *(Note: You can later replace these mocks with real HTML snapshots downloaded from the websites).*

---

### Concrete Scraper Implementations

#### [NEW] [src/scrapers/kabum.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/scrapers/kabum.py)
We will implement the `KabumScraper` strategy inheriting from `BaseScraper`. 
- `fetch()` will be a stub (or pass-through) utilizing the injected HTTP/Browser client.
- `parse()` will use BeautifulSoup to extract data from the Kabum HTML structure and return a list of validated `PriceContract` models.

#### [NEW] [src/scrapers/terabyte.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/src/scrapers/terabyte.py)
We will implement the `TerabyteScraper` strategy mirroring the architecture of the Kabum scraper but tailored to Terabyte's HTML structure.

---

### Unit Tests (TDD)

#### [NEW] [tests/unit/test_parsers.py](file:///c:/Users/Eduardo/Documents/Github/pricing-alert/tests/unit/test_parsers.py)
We will write deterministic unit tests utilizing `pytest`. 
- The tests will load the static HTML fixtures from disk.
- They will invoke the `parse()` methods on both `KabumScraper` and `TerabyteScraper`.
- They will assert that the returned data exactly matches the expected `PriceContract` fields (correct prices, titles, URLs, and UTC timestamps), ensuring 100% test coverage for the parsing logic without making a single network request.

## User Review Required

> [!IMPORTANT]
> To proceed, I will add `beautifulsoup4` and `lxml` to the dependencies, create mock HTML fixtures, build the scrapers, and write the deterministic tests. 
> 
> *Do you approve this plan and the addition of the BeautifulSoup dependencies?*

## Verification Plan

### Automated Tests
- We will execute the Pytest suite specifically targeting `tests/unit/test_parsers.py` to prove that the parsers correctly extract and validate data from the static fixtures.

### Manual Verification
- Review the `parse()` implementations in `kabum.py` and `terabyte.py` to ensure they contain absolutely no network request code.
