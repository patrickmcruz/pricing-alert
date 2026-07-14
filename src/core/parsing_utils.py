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
