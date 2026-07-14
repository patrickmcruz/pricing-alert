"""
Normalized GPU catalog entities: Brand (board partner, e.g. MSI), GpuChipset
(the NVIDIA/AMD reference, e.g. "rtx 5070 ti"), and GpuModel (a specific
brand+chipset+variant combination, e.g. MSI "Shadow 2X OC" RTX 5070 Ti).

These replace the free-text brand/model fields that used to live directly on
ProductSKU - see src/repositories/catalog_repository.py for the persistence
layer that resolves/dedupes these.
"""

from __future__ import annotations

from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


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


class Brand(BaseModel):
    """A board partner / AIB, e.g. MSI, Gainward, XFX."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str


class GpuChipset(BaseModel):
    """
    The NVIDIA/AMD chip reference, independent of board partner.

    `name` is kept lowercase to match the existing `search_keyword` convention
    (e.g. "rtx 5070 ti"), not a Title-Case display string - this is what lets
    search_keyword keep working as a plain string everywhere without a casing
    discontinuity against historical price records.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    chip_maker: ChipMaker = ChipMaker.UNKNOWN


class GpuModel(BaseModel):
    """A specific product: a Brand's variant of a GpuChipset, e.g. MSI "Shadow 2X OC" RTX 5070 Ti."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    brand_id: str
    chipset_id: str
    variant_name: str


class ResolvedGpuModel(BaseModel):
    """Read-only DTO joining a GpuModel with its Brand/GpuChipset names, for display."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    brand_name: str
    chipset_name: str
    variant_name: str
