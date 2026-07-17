import pytest
from src.core.browser import BrowserFactory
from src.scrapers.kabum import KabumScraper
from src.core.contract import ProductSKU

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_kabum_smoke():
    """
    Real network E2E test for Kabum parser.
    Hits a live product URL and verifies we get a valid PriceContract back.
    Requires internet access and real Playwright browser.
    """
    factory = BrowserFactory()
    scraper = KabumScraper()
    
    # We use a real SKU URL from seed
    sku = ProductSKU(
        product_url="https://www.kabum.com.br/produto/875474/placa-de-video-msi-rtx-5070-12gb-gddr7-192-bits-shadow-2x-oc-912-v532-011",
        store_name="kabum",
        search_keyword="rtx 5070",
        produto_id="test-produto-id",
        brand="MSI",
        model="Shadow 2x OC",
        product_title="RTX 5070"
    )
    
    client = await factory.create(scraper)
    try:
        price_contract = await scraper.execute(sku, client)
        
        # Verify it successfully downloaded and parsed data
        assert price_contract is not None
        assert price_contract.store_name == "kabum"
        assert price_contract.price_cash > 0
        assert price_contract.is_available in (True, False)  # It's okay if out of stock, it should still parse
        
        if price_contract.is_available:
            assert price_contract.price_installments is not None
            assert price_contract.installment_count is not None
            assert price_contract.installment_count > 0
    finally:
        await factory.close(client)
