from bs4 import BeautifulSoup

from src.core.parsing_utils import has_maintenance_marker


def _soup(title: str) -> BeautifulSoup:
    return BeautifulSoup(f"<html><head><title>{title}</title></head><body></body></html>", "lxml")


def test_detects_default_portuguese_maintenance_marker():
    assert has_maintenance_marker(_soup("Site em Manutenção - Pru Pru")) is True


def test_detects_default_english_maintenance_marker():
    assert has_maintenance_marker(_soup("503 Service Unavailable")) is True


def test_is_case_insensitive():
    assert has_maintenance_marker(_soup("SITE EM MANUTENÇÃO")) is True


def test_returns_false_for_a_real_product_page_title():
    assert has_maintenance_marker(_soup("MSI GeForce RTX 5070 Ti 16GB - Pichau")) is False


def test_returns_false_when_there_is_no_title_tag():
    soup = BeautifulSoup("<html><body>No title here</body></html>", "lxml")
    assert has_maintenance_marker(soup) is False


def test_accepts_custom_marker_list():
    soup = _soup("Voltamos já - aguarde")
    assert has_maintenance_marker(soup) is False
    assert has_maintenance_marker(soup, markers=("voltamos já",)) is True
