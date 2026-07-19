"""
Tests parse_search_results() against synthetic fixture HTML reproducing the
real shape of a Pichau search-results page (Next.js RSC payload embedding
the GraphQL product list) - see tests/unit/test_pichau_parser.py and
src.scrapers.pichau.extract_pichau_products for the same mechanism - plus
discover()'s own orchestration logic (dedup, abort-when-unavailable), which
parse_search_results()'s tests don't reach since they only exercise the
pure helper, not the async function that drives it.
"""
import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

import scripts.discover_pichau_gpus as discover_pichau_gpus
from src.core.base_scraper import StoreUnavailableException
from src.core.contract import TargetUrlEntry
from scripts.discover_pichau_gpus import _matches_chipset, parse_search_results


def _product(**overrides) -> dict:
    product = {
        "id": 1,
        "sku": "MSI-5070TI-16G",
        "name": "MSI GeForce RTX 5070 Ti 16GB",
        "url_key": "placa-de-video-msi-geforce-rtx-5070-ti-16gb",
        "marcas_info": {"name": "MSI"},
        "pichau_prices": {
            "avista": 4799.00,
            "avista_discount": 15,
            "avista_method": "PIX",
            "base_price": 5599.00,
            "final_price": 5299.00,
            "max_installments": 12,
        },
        "stock_status": "IN_STOCK",
    }
    product.update(overrides)
    return product


def _page(*products: dict, title: str = "Busca por: 5070 | Pichau") -> str:
    inner = json.dumps({"products": {"items": list(products)}}, separators=(",", ":"))
    push_arg = json.dumps([1, f"6:{inner}\n"], separators=(",", ":"))
    return f"<html><head><title>{title}</title></head><body><script>self.__next_f.push({push_arg})</script></body></html>"


def test_matches_chipset_distinguishes_ti_from_plain():
    assert _matches_chipset("MSI GeForce RTX 5070 Ti 16GB", "rtx 5070 ti") is True
    assert _matches_chipset("MSI GeForce RTX 5070 Ti 16GB", "rtx 5070") is False
    assert _matches_chipset("MSI GeForce RTX 5070 12GB", "rtx 5070") is True
    assert _matches_chipset("MSI GeForce RTX 5070 12GB", "rtx 5070 ti") is False


def test_matches_chipset_handles_query_style_ti_notation():
    assert _matches_chipset("Placa de Video RTX 5070T.I Gaming", "rtx 5070 ti") is True
    assert _matches_chipset("Placa de Video RTX 5070TI Gaming", "rtx 5070 ti") is True


def test_parse_search_results_extracts_matching_products():
    html = _page(
        _product(),
        _product(sku="ZOTAC-5070TI", name="Zotac Gaming RTX 5070 Ti Twin Edge",
                  url_key="placa-de-video-zotac-rtx-5070-ti", marcas_info={"name": "Zotac"}),
    )

    results = parse_search_results(html, "rtx 5070 ti")

    assert len(results) == 2
    assert results[0]["product_title"] == "MSI GeForce RTX 5070 Ti 16GB"
    assert results[0]["product_url"] == "https://www.pichau.com.br/placa-de-video-msi-geforce-rtx-5070-ti-16gb"
    assert results[0]["brand"] == "MSI"
    assert results[0]["search_keyword"] == "rtx 5070 ti"
    assert results[0]["store_name"] == "pichau"
    assert results[0]["_discovered_price_cash"] == Decimal("4799.00")


def test_parse_search_results_filters_out_non_matching_chipsets():
    html = _page(
        _product(),
        _product(sku="MSI-5060", name="MSI GeForce RTX 5060 8GB", url_key="placa-msi-rtx-5060"),
    )

    results = parse_search_results(html, "rtx 5070 ti")

    assert len(results) == 1
    assert "5060" not in results[0]["product_title"]


def test_parse_search_results_deduplicates_by_sku():
    # Real pages repeat the same product object across multiple RSC chunks
    # (e.g. once in the grid, once in a "recently viewed" widget).
    html = _page(_product(), _product())

    results = parse_search_results(html, "rtx 5070 ti")

    assert len(results) == 1


def test_parse_search_results_tolerates_missing_brand():
    html = _page(_product(marcas_info=None))

    results = parse_search_results(html, "rtx 5070 ti")

    assert len(results) == 1
    assert results[0]["brand"] is None


def test_parse_search_results_returns_empty_when_no_products_embedded():
    html = "<html><head><title>Busca por: 5070 | Pichau</title></head><body>no results</body></html>"

    assert parse_search_results(html, "rtx 5070 ti") == []


def test_parse_search_results_raises_store_unavailable_for_a_maintenance_page():
    # The actual condition pichau.com.br was in while this store was first
    # scoped - a maintenance page embeds no product JSON either, for a
    # different reason than a real "no matches" result, and this is what
    # tells them apart instead of silently reporting "0 candidates found".
    html = "<html><head><title>Site em Manutenção - Pichau</title></head><body></body></html>"

    with pytest.raises(StoreUnavailableException):
        parse_search_results(html, "rtx 5070 ti")


def _target_url_entry(product_url: str, **overrides) -> TargetUrlEntry:
    fields = {
        "store_name": "pichau",
        "search_keyword": "rtx 5070",
        "product_url": product_url,
        "brand": "MSI",
        "model": None,
        "product_title": "Existing product",
    }
    fields.update(overrides)
    return TargetUrlEntry(**fields)


def _found_row(product_url: str, search_keyword: str = "rtx 5070") -> dict:
    return {
        "store_name": "pichau",
        "search_keyword": search_keyword,
        "product_url": product_url,
        "brand": "MSI",
        "model": None,
        "product_title": "Found product",
        "_discovered_price_cash": Decimal("100.00"),
    }


@pytest.fixture
def patched_discover(monkeypatch):
    """
    discover() drives real network I/O (Playwright) and a real DB repository
    internally - patches those construction points so its own orchestration
    logic (dedup against existing rows and within a single run, aborting
    without writing when every search query is unavailable) can be tested
    without either. parse_search_results() itself is patched too, since its
    own correctness is already covered by the tests above - these tests are
    only about what discover() does with what parse_search_results returns.
    """
    fake_page = MagicMock()
    fake_page.goto = AsyncMock(return_value=None)
    fake_page.content = AsyncMock(return_value="<html></html>")

    fake_factory = MagicMock()
    fake_factory.create = AsyncMock(return_value=fake_page)
    fake_factory.close = AsyncMock(return_value=None)
    monkeypatch.setattr(discover_pichau_gpus, "BrowserFactory", MagicMock(return_value=fake_factory))

    monkeypatch.setattr(discover_pichau_gpus, "initialize_db_schema", AsyncMock(return_value=None))

    fake_repo = MagicMock()
    fake_repo.list_all = AsyncMock(return_value=[])
    fake_repo.upsert_many = AsyncMock(return_value=0)
    monkeypatch.setattr(discover_pichau_gpus, "PostgresTargetUrlRepository", MagicMock(return_value=fake_repo))

    return fake_repo


@pytest.mark.asyncio
async def test_discover_dedupes_against_existing_rows_and_within_the_same_run(monkeypatch, patched_discover):
    fake_repo = patched_discover
    fake_repo.list_all = AsyncMock(return_value=[_target_url_entry("https://www.pichau.com.br/existing")])

    def fake_parse_search_results(html, search_keyword):
        if search_keyword == "rtx 5070":
            return [_found_row("https://www.pichau.com.br/existing"), _found_row("https://www.pichau.com.br/new-1")]
        return [_found_row("https://www.pichau.com.br/new-1", search_keyword), _found_row("https://www.pichau.com.br/new-2", search_keyword)]

    monkeypatch.setattr(discover_pichau_gpus, "parse_search_results", fake_parse_search_results)

    await discover_pichau_gpus.discover()

    fake_repo.upsert_many.assert_called_once()
    written_urls = {entry.product_url for entry in fake_repo.upsert_many.call_args[0][0]}
    assert written_urls == {"https://www.pichau.com.br/new-1", "https://www.pichau.com.br/new-2"}


@pytest.mark.asyncio
async def test_discover_aborts_without_writing_when_every_query_is_unavailable(monkeypatch, patched_discover):
    fake_repo = patched_discover

    def fake_parse_search_results(html, search_keyword):
        raise StoreUnavailableException("[pichau] Store appears to be down for maintenance.")

    monkeypatch.setattr(discover_pichau_gpus, "parse_search_results", fake_parse_search_results)

    await discover_pichau_gpus.discover()

    fake_repo.upsert_many.assert_not_called()


@pytest.mark.asyncio
async def test_discover_continues_when_only_one_query_is_unavailable(monkeypatch, patched_discover):
    fake_repo = patched_discover

    def fake_parse_search_results(html, search_keyword):
        if search_keyword == "rtx 5070":
            raise StoreUnavailableException("[pichau] Store appears to be down for maintenance.")
        return [_found_row("https://www.pichau.com.br/new-1", search_keyword)]

    monkeypatch.setattr(discover_pichau_gpus, "parse_search_results", fake_parse_search_results)

    await discover_pichau_gpus.discover()

    fake_repo.upsert_many.assert_called_once()
    written_urls = {entry.product_url for entry in fake_repo.upsert_many.call_args[0][0]}
    assert written_urls == {"https://www.pichau.com.br/new-1"}
