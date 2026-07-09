# Terabyte Spider and Scraper Implementation Walkthrough

The development of the spider and scraper for the `terabyteshop.com.br` engine has been successfully completed, integrating the requested CSS selectors and following the architecture of the `pricing-alert` repository.

## Changes Made

1. **Configuration ([terabyte.toml](file:///c:/Users/patrickcruz/Documents/2026/Pessoal/Github/pricing-alert/data/selectors/terabyte.toml))**
   - Externalized the new CSS selectors provided by the user.
   - Updated `price_installments` to use `#valParc`.
   - Added the new `installment_count` selector mapped to `#nParc`.

2. **Scraping Engine ([terabyte.py](file:///c:/Users/patrickcruz/Documents/2026/Pessoal/Github/pricing-alert/src/scrapers/terabyte.py))**
   - Updated `TerabyteScraper.parse()` to extract the text from the `installment_count` selector.
   - Implemented regex logic to reliably convert the extracted text into an integer representing the maximum number of installments (e.g., extracting `12` from `12x`).
   - Integrated `installment_count` into the unified `PriceContract` data model.

3. **Discovery Engine ([terabyte_spider.py](file:///c:/Users/patrickcruz/Documents/2026/Pessoal/Github/pricing-alert/src/spiders/terabyte_spider.py))**
   - Implemented the `fetch_search_page` method utilizing the repository's asynchronous HTTP client interface.
   - Handled URL encoding of the search queries to securely construct valid `terabyteshop.com.br/busca` search URLs.
   - Fixed pre-existing minor linting issues (`ruff` multiple-statement lines) in the file for better compliance with style guidelines.

## Verification

The new implementations have been validated through the project's strict test gates:

- **Unit Testing**:
  - The static mock fixture `terabyte_product_mock.html` was updated to accurately mirror Terabyte's current DOM structure with the new IDs.
  - Assertions were successfully added and validated for `installment_count` in `test_parsers.py`.
  - Result: `2 passed in 0.48s`.
- **Quality Gates**:
  - **Mypy**: Successfully completed type checks without issues in `src/scrapers` and `src/spiders`.
  - **Ruff**: Resolved minor unused imports and stylistic formatting issues, ensuring code cleanliness.

## Next Steps

With the Terabyte engine now capable of discovering SKUs and extracting precise pricing/installment constraints, you are ready to use this engine to perform the extraction of RTX 5070 cards using the system orchestrator or add them to the cron schedule.
