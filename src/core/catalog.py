"""
Normalized product catalog entities: Categoria (product category, e.g. "GPU",
"Notebook"), Marca (brand/board partner, e.g. MSI), and Produto (a specific
brand+category+variant combination, e.g. MSI "Shadow 2X OC" RTX 5070 Ti).
Category-specific attributes that don't warrant their own column (VRAM,
chipset, RAM, litros...) live in Produto.specs instead of a wider table.

These replace the free-text brand/model fields that used to live directly on
ProductSKU - see src/repositories/catalog_repository.py for the persistence
layer that resolves/dedupes these.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

# The category slug every GPU scraper/discovery flow resolves into today.
# Other categories (notebooks, geladeiras...) get their own slug the first
# time DiscoveryEngine (or a future scraper) resolves a product into them -
# see CatalogRepository.get_or_create_categoria.
GPU_CATEGORY_SLUG = "gpu"


class ChipMaker(str, Enum):
    NVIDIA = "NVIDIA"
    AMD = "AMD"
    UNKNOWN = "UNKNOWN"


def infer_chip_maker(chipset_name: str) -> ChipMaker:
    """Best-effort guess from a chipset name, e.g. "rtx 5070 ti" -> NVIDIA."""
    name = chipset_name.lower()
    if "rtx" in name or "gtx" in name:
        return ChipMaker.NVIDIA
    if "rx" in name or "radeon" in name:
        return ChipMaker.AMD
    return ChipMaker.UNKNOWN


class Categoria(BaseModel):
    """A product category, e.g. GPU, Notebook. Self-referencing for optional hierarchy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    nome: str
    slug: str
    parent_id: str | None = None


class Marca(BaseModel):
    """A brand / board partner, e.g. MSI, Gainward, XFX."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    nome: str


class Produto(BaseModel):
    """
    A canonical product: a Marca's item within a Categoria, e.g. MSI "Shadow
    2X OC" RTX 5070 Ti. Category-specific attributes (chipset, VRAM, RAM,
    litros...) live in `specs` rather than as dedicated columns, so adding a
    new product category doesn't require a schema change.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    marca_id: str
    categoria_id: str
    nome: str
    mpn: str | None = None
    product_line: str | None = None
    is_oc: bool = False
    gtin: str | None = None
    specs: dict[str, Any] = Field(default_factory=dict)


class ResolvedProduto(BaseModel):
    """Read-only DTO joining a Produto with its Marca/Categoria names, for display."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    marca_nome: str
    categoria_nome: str
    nome: str
    mpn: str | None = None
    product_line: str | None = None
    is_oc: bool = False
    specs: dict[str, Any] = Field(default_factory=dict)
