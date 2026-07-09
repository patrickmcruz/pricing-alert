# Develop Terabyte Spider and Scraper

The goal is to develop the `TerabyteSpider` and `TerabyteScraper` to extract RTX 5070 pricing data from `terabyteshop.com.br`, specifically utilizing the CSS selectors provided for cash price, installment price, and installment count.

## Proposed Changes

### Configuration
Update the externalized TOML configuration for Terabyte with the provided CSS selectors.

#### [MODIFY] [terabyte.toml](file:///c:/Users/patrickcruz/Documents/2026/Pessoal/Github/pricing-alert/data/selectors/terabyte.toml)
- Change `price_installments` to `"#valParc"` (was previously `#valParcel`).
- Add `installment_count = "#nParc"`.

---

### Scraper Engine
Update the scraping logic to extract the newly added installment count.

#### [MODIFY] [terabyte.py](file:///c:/Users/patrickcruz/Documents/2026/Pessoal/Github/pricing-alert/src/scrapers/terabyte.py)
- Extract the installment count using the new `#nParc` selector.
- Parse the extracted string to an integer.
- Include `installment_count` in the `PriceContract` returned by the `parse` method.

---

### Discovery Engine (Spiders)
Implement network fetching for the search grid.

#### [MODIFY] [terabyte_spider.py](file:///c:/Users/patrickcruz/Documents/2026/Pessoal/Github/pricing-alert/src/spiders/terabyte_spider.py)
- Implement `fetch_search_page(self, keyword: str, client: Any) -> str`.
- Encode the `keyword` and send a GET request to Terabyte's search endpoint: `https://www.terabyteshop.com.br/busca?str={keyword}`.

---

### Tests
Update test fixtures and unit tests to validate the newly updated parsing logic.

#### [MODIFY] [terabyte_product_mock.html](file:///c:/Users/patrickcruz/Documents/2026/Pessoal/Github/pricing-alert/tests/fixtures/terabyte_product_mock.html)
- Update `<p id="valParcel">` to `<p id="valParc">`.
- Add an element for installment count, e.g., `<span id="nParc">12x</span>`.

#### [MODIFY] [test_parsers.py](file:///c:/Users/patrickcruz/Documents/2026/Pessoal/Github/pricing-alert/tests/unit/test_parsers.py)
- Add assertions in `test_terabyte_product_parser` to verify the extraction of `installment_count`.

## Verification Plan

### Automated Tests
- Run `pytest tests/unit/test_parsers.py` to ensure the scraper correctly extracts all values deterministically from the mock HTML.

### Quality Gates
- Run `mypy src/scrapers src/spiders` to verify static typing.
- Run `ruff check src/scrapers src/spiders` for linting.
