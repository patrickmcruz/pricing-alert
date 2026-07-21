from __future__ import annotations

import re
from decimal import Decimal
from typing import Pattern

from bs4 import BeautifulSoup

_PRICE_NOISE_RE = re.compile(r"[R\$\s\.]")


def clean_brl_price(price_str: str | None) -> Decimal | None:
    """Converts a BRL price string (e.g. 'R$ 5.499,99') to a Decimal."""
    if not price_str:
        return None
    cleaned = _PRICE_NOISE_RE.sub("", price_str).replace(",", ".")
    try:
        return Decimal(cleaned)
    except Exception:
        return None


def compute_discount(
    price_cash: Decimal | None, price_installments: Decimal | None
) -> Decimal | None:
    """Computes the discount between the installment total and the cash price."""
    if price_installments and price_installments > 0 and price_cash and price_cash > 0:
        return price_installments - price_cash
    return None


def has_out_of_stock_marker(soup: BeautifulSoup, pattern: str | Pattern[str]) -> bool:
    """Checks whether the document contains an out-of-stock text marker."""
    regex = pattern if isinstance(pattern, re.Pattern) else re.compile(pattern, re.I)
    return soup.find(string=regex) is not None


# Phrases stores commonly show instead of real content when they're down for
# maintenance, rather than when a scraper's own selectors have drifted.
# Deliberately checked against <title> only (see has_maintenance_marker) -
# body text is far more likely to contain an incidental false-positive match
# (e.g. a product review mentioning "manutenção").
DEFAULT_MAINTENANCE_MARKERS = (
    "em manutenção",
    "under maintenance",
    "site indisponível",
    "service unavailable",
    "server error",
)


def has_maintenance_marker(
    soup: BeautifulSoup, markers: tuple[str, ...] = DEFAULT_MAINTENANCE_MARKERS
) -> bool:
    """
    Checks the document's <title> for a known "store is down" phrase, so a
    maintenance page can be told apart from a real page whose selectors have
    gone stale - the two otherwise look identical to a scraper (a title
    element that doesn't match `selectors["title"]`). Scrapers should call
    this first in parse() and raise StoreUnavailableException
    (src.core.base_scraper) rather than letting it fall through to
    SelectorOutdatedException, which would misreport a store outage as a
    selector needing an update.
    """
    title = soup.title.get_text(strip=True).lower() if soup.title else ""
    return any(marker in title for marker in markers)


_TITLE_TAG_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def has_maintenance_marker_in_html(
    html: str, markers: tuple[str, ...] = DEFAULT_MAINTENANCE_MARKERS
) -> bool:
    """
    Same check as has_maintenance_marker(), for scrapers that extract data
    straight from the raw HTML/JSON text (see src.scrapers.pichau) instead of
    a BeautifulSoup tree - avoids building a full DOM just to read <title>.
    The maintenance banner may appear in either the document title or the body
    text, so we inspect both.
    """
    match = _TITLE_TAG_RE.search(html)
    title = match.group(1).strip().lower() if match else ""
    if any(marker in title for marker in markers):
        return True

    text = re.sub(r"<[^>]+>", " ", html).lower()
    return any(marker in text for marker in markers)
