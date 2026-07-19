"""
Tests parse_search_results() against synthetic fixture HTML reproducing the
real shape of a Pichau search-results page (Next.js RSC payload embedding
the GraphQL product list) - see tests/unit/test_pichau_parser.py and
src.scrapers.pichau.extract_pichau_products for the same mechanism.
"""
import json
from decimal import Decimal

import pytest

from src.core.base_scraper import StoreUnavailableException
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
