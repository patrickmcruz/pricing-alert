from abc import ABC, abstractmethod
from typing import List, Optional

from src.core.catalog import Brand, ChipMaker, GpuChipset, GpuModel, ResolvedGpuModel


class CatalogRepository(ABC):
    """
    Abstract interface for the normalized GPU catalog: Brand (board partner),
    GpuChipset (the NVIDIA/AMD reference), and GpuModel (a specific
    brand+chipset+variant). target_urls/prices reference GpuModel by id
    instead of storing free-text brand/model.
    """

    @abstractmethod
    async def get_or_create_brand(self, name: str) -> Brand:
        """Case-insensitive get-or-create by name."""

    @abstractmethod
    async def get_or_create_chipset(
        self, name: str, chip_maker: ChipMaker = ChipMaker.UNKNOWN
    ) -> GpuChipset:
        """Case-insensitive get-or-create by name."""

    @abstractmethod
    async def get_or_create_gpu_model(
        self, brand_id: str, chipset_id: str, model_name: str
    ) -> GpuModel:
        """Case-insensitive get-or-create by (brand_id, chipset_id, model_name)."""

    @abstractmethod
    async def get_gpu_model(self, gpu_model_id: str) -> Optional[GpuModel]:
        """Returns a GpuModel by id, or None if it doesn't exist."""

    @abstractmethod
    async def list_brands(self) -> List[Brand]: ...

    @abstractmethod
    async def list_chipsets(self) -> List[GpuChipset]: ...

    @abstractmethod
    async def list_gpu_models_resolved(self) -> List[ResolvedGpuModel]:
        """Every GpuModel joined with its Brand/GpuChipset names, for display."""
