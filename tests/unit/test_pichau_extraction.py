"""
Tests extract_pichau_products() directly against malformed/partial RSC
payloads - the happy path is already covered indirectly through
test_pichau_parser.py/test_discover_pichau_gpus.py, but neither exercises
the two defensive `except json.JSONDecodeError` branches inside the
function itself (a push() call whose argument isn't valid JSON once
captured, and an embedded product object that's truncated/malformed at the
position the anchor regex found). A real page can plausibly serve a
truncated response (network cutoff, a proxy buffering issue) - these tests
confirm that degrades to "skip this one, keep going" rather than a crash.
"""
import json

from src.scrapers.pichau import extract_pichau_products


def _good_push(product_id: int, sku: str) -> str:
    product = {
        "id": product_id,
        "sku": sku,
        "name": f"Placa de Video Good {sku}",
        "url_key": f"placa-{sku.lower()}",
        "marcas_info": {"name": "MSI"},
        "pichau_prices": {"avista": 100.0, "base_price": 120.0, "max_installments": 12},
        "stock_status": "IN_STOCK",
    }
    inner = json.dumps({"products": {"items": [product]}}, separators=(",", ":"))
    push_arg = json.dumps([1, f"6:{inner}\n"], separators=(",", ":"))
    return f"<script>self.__next_f.push({push_arg})</script>"


def test_extract_pichau_products_returns_the_valid_product_from_a_good_page():
    html = f"<html><body>{_good_push(1, 'GOOD-1')}</body></html>"

    products = extract_pichau_products(html)

    assert len(products) == 1
    assert products[0]["sku"] == "GOOD-1"


def test_extract_pichau_products_skips_a_push_call_with_an_invalid_json_escape():
    # `\q` is not a valid JSON escape sequence - the outer push() argument
    # matches _PUSH_ARG_RE syntactically (any backslash+char is accepted by
    # the regex's permissive [^"\\]|\\. alternation) but fails json.loads(),
    # which is what the first `except (json.JSONDecodeError, ValueError)`
    # branch in extract_pichau_products exists to catch.
    broken_push = r'<script>self.__next_f.push([1,"6:{\"id\":1,\"sku\":\"BAD\",\q}"])</script>'
    html = f"<html><body>{broken_push}{_good_push(2, 'GOOD-2')}</body></html>"

    products = extract_pichau_products(html)

    assert len(products) == 1
    assert products[0]["sku"] == "GOOD-2"


def test_extract_pichau_products_skips_a_truncated_product_object():
    # The outer push() argument is valid JSON (a real int + string), but the
    # un-escaped payload's product object is cut off mid-string - anchor
    # matching still finds where it starts, but json.JSONDecoder.raw_decode
    # can't read a complete value from there, hitting the second
    # `except json.JSONDecodeError` branch.
    truncated_inner = '6:{"id":2,"sku":"BROKEN'
    truncated_push_arg = json.dumps([1, truncated_inner], separators=(",", ":"))
    truncated_push = f"<script>self.__next_f.push({truncated_push_arg})</script>"
    html = f"<html><body>{truncated_push}{_good_push(3, 'GOOD-3')}</body></html>"

    products = extract_pichau_products(html)

    assert len(products) == 1
    assert products[0]["sku"] == "GOOD-3"


def test_extract_pichau_products_returns_empty_list_for_html_with_no_push_calls():
    assert extract_pichau_products("<html><body>nothing here</body></html>") == []
