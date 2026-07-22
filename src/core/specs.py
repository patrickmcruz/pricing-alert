from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class VRAMSpec(BaseModel):
    """VRAM details for a GPU."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    capacity_gb: int = Field(default=0, description="VRAM capacity in Gigabytes (e.g. 16)")
    memory_type: str = Field(default="GDDR6", description="Memory type (e.g. GDDR7, GDDR6X)")


class GPUSpecs(BaseModel):
    """Category-specific specs for Placa de Vídeo (GPU)."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    chipset: str = Field(..., description="GPU chipset model (e.g. 'RTX 5070 Ti', 'RX 7900 XT')")
    chip_maker: str = Field(default="NVIDIA", description="Chip maker (NVIDIA, AMD, Intel)")
    vram_gb: int = Field(default=0, description="VRAM capacity in GB")
    vram_type: str = Field(default="GDDR6", description="VRAM memory type")
    is_oc: bool = Field(default=False, description="Factory Overclocked")
    form_factor: Optional[str] = Field(default=None, description="Form factor (e.g. SFF, ATX, Dual-Slot)")
    product_line: Optional[str] = Field(default=None, description="Product line / cooler brand (e.g. Windforce, TUF)")
    mpn: Optional[str] = Field(default=None, description="Manufacturer Part Number / SKU")
    features: List[str] = Field(default_factory=list, description="Supported features (e.g. DLSS, Ray Tracing)")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class MotherboardSpecs(BaseModel):
    """Category-specific specs for Placa Mãe (Motherboard)."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    socket: str = Field(..., description="CPU Socket (e.g. AM5, LGA1700, LGA1851)")
    chipset: str = Field(..., description="Motherboard Chipset (e.g. B650, Z790, X870)")
    form_factor: str = Field(default="ATX", description="Form factor (e.g. ATX, Micro-ATX, Mini-ITX)")
    memory_type: str = Field(default="DDR5", description="Supported memory type (e.g. DDR5, DDR4)")
    memory_slots: int = Field(default=4, description="Number of RAM slots")
    max_memory_gb: Optional[int] = Field(default=None, description="Maximum supported RAM capacity in GB")
    product_line: Optional[str] = Field(default=None, description="Product line (e.g. AORUS, ROG Strix)")
    mpn: Optional[str] = Field(default=None, description="Manufacturer Part Number")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class RAMSpecs(BaseModel):
    """Category-specific specs for Memória RAM."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    capacity_gb: int = Field(..., description="Total kit capacity in GB (e.g. 32)")
    module_count: int = Field(default=1, description="Number of modules in kit (e.g. 2 for 2x16GB)")
    memory_type: str = Field(default="DDR5", description="Memory type (e.g. DDR5, DDR4)")
    speed_mhz: int = Field(..., description="Memory speed in MHz (e.g. 6000)")
    latency_cl: Optional[str] = Field(default=None, description="CAS Latency (e.g. CL30)")
    has_rgb: bool = Field(default=False, description="Whether module includes RGB lighting")
    product_line: Optional[str] = Field(default=None, description="Product line (e.g. Vengeance, Fury Beast)")
    mpn: Optional[str] = Field(default=None, description="Manufacturer Part Number")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class CPUSpecs(BaseModel):
    """Category-specific specs for Processador / CPU."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    socket: str = Field(..., description="CPU Socket (e.g. AM5, AM4, LGA1851, LGA1700)")
    manufacturer: str = Field(default="AMD", description="CPU Manufacturer (AMD or Intel)")
    model_family: str = Field(..., description="CPU Family (e.g. Ryzen 7, Ryzen 5, Core i7, Core Ultra 7)")
    model_number: str = Field(..., description="CPU Model Number (e.g. 9800X3D, 7800X3D, 14700K, 265K)")
    cores: Optional[int] = Field(default=None, description="Number of CPU Cores")
    threads: Optional[int] = Field(default=None, description="Number of CPU Threads")
    base_clock_ghz: Optional[float] = Field(default=None, description="Base Clock in GHz")
    boost_clock_ghz: Optional[float] = Field(default=None, description="Boost/Turbo Clock in GHz")
    has_integrated_gpu: bool = Field(default=False, description="Has Integrated Graphics iGPU")
    mpn: Optional[str] = Field(default=None, description="Manufacturer Part Number")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
