import os
import re
import tomllib
from typing import Any, Dict, List, Optional, Tuple

from src.core.specs import GPUSpecs, MotherboardSpecs, RAMSpecs

PARSERS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "parsers"))


def _load_toml_config(filename: str) -> dict:
    filepath = os.path.join(PARSERS_DIR, filename)
    if os.path.exists(filepath):
        try:
            with open(filepath, "rb") as f:
                return tomllib.load(f)
        except Exception:
            pass
    return {}


class TitleParserRegistry:
    """
    Registry for category-specific product title parsers.
    Parses unstructured retailer titles into typed specs models using TOML configs.
    """

    @staticmethod
    def parse_gpu(raw_title: str | None, search_keyword: str = "") -> GPUSpecs:
        title = raw_title or ""
        title_upper = title.upper()
        config = _load_toml_config("gpu.toml")

        # 1. Chipset
        pattern = config.get("patterns", {}).get(
            "chipset",
            r"\b(RTX\s*\d{4}(?:\s*TI)?|GTX\s*\d{4}(?:\s*TI)?|RX\s*\d{4}(?:\s*XTX|\s*XT|\s*GRE)?)\b",
        )
        chipset_match = re.search(pattern, title, re.IGNORECASE)
        if chipset_match:
            chipset_model = re.sub(r"\s+", " ", chipset_match.group(1).upper())
        else:
            kw_clean = search_keyword.strip().upper()
            chipset_model = kw_clean if kw_clean else "RTX 5070"

        # Chip maker
        if "RX" in chipset_model or "RADEON" in title_upper:
            chip_maker = "AMD"
        elif "ARC" in title_upper or "INTEL" in title_upper:
            chip_maker = "Intel"
        else:
            chip_maker = "NVIDIA"

        # 2. VRAM
        vram_match = re.search(r"\b(\d{1,2})\s*GB\b", title, re.IGNORECASE)
        vram_gb = int(vram_match.group(1)) if vram_match else 12

        vtype_match = re.search(r"\b(GDDR7|GDDR6X|GDDR6|GDDR5X|GDDR5)\b", title, re.IGNORECASE)
        vram_type = vtype_match.group(1).upper() if vtype_match else "GDDR7"

        # 3. OC / Form factor
        is_oc = bool(re.search(r"\b(OC|OVERCLOCK|OVERCLOCKED)\b", title_upper))

        form_factor = None
        if "SFF" in title_upper or "SMALL FORM FACTOR" in title_upper:
            form_factor = "SFF"
        elif "DUAL-SLOT" in title_upper or "DUAL SLOT" in title_upper:
            form_factor = "Dual-Slot"
        elif "TRIPLE SLOT" in title_upper or "3-SLOT" in title_upper:
            form_factor = "Triple-Slot"

        # 4. Product Line / Cooler
        product_line = None
        known_lines = [
            "WINDFORCE", "EAGLE", "AORUS", "GAMING OC", "TUF GAMING", "ROG STRIX", "DUAL",
            "VENTUS", "GAMING X", "SUPRIM", "SHADOW", "TRINITY", "AMP EXTREME", "EPIC-X",
            "PEGASUS", "GAMINGPRO", "STEEL LEGEND", "TAICHI", "HELLHOUND", "RED DEVIL"
        ]
        for line in known_lines:
            if line in title_upper:
                product_line = line.title()
                break

        # 5. MPN / SKU Code
        mpn_match = re.search(r"\b([A-Z0-9]{3,}-[A-Z0-9]{3,}|GV-[A-Z0-9]+|VCG[A-Z0-9]+|NE[A-Z0-9]+|ZT-[A-Z0-9-]+)\b", title)
        mpn = mpn_match.group(1) if mpn_match else None

        # 6. Features
        features = []
        if "DLSS" in title_upper:
            features.append("DLSS")
        if "RAY TRACING" in title_upper or "RAYTRACING" in title_upper:
            features.append("Ray Tracing")

        return GPUSpecs(
            chipset=chipset_model,
            chip_maker=chip_maker,
            vram_gb=vram_gb,
            vram_type=vram_type,
            is_oc=is_oc,
            form_factor=form_factor,
            product_line=product_line,
            mpn=mpn,
            features=features,
        )

    @staticmethod
    def parse_motherboard(raw_title: str | None) -> MotherboardSpecs:
        title = raw_title or ""
        title_upper = title.upper()

        # Socket
        socket = "AM5"
        if "AM5" in title_upper:
            socket = "AM5"
        elif "AM4" in title_upper:
            socket = "AM4"
        elif "LGA1700" in title_upper or "LGA 1700" in title_upper:
            socket = "LGA1700"
        elif "LGA1851" in title_upper or "LGA 1851" in title_upper:
            socket = "LGA1851"

        # Chipset
        chipset_match = re.search(r"\b(B650[M]?|X670[E]?|X870[E]?|B850[M]?|Z790|B760[M]?|H610[M]?|Z890)\b", title_upper)
        chipset = chipset_match.group(1) if chipset_match else "B650"

        # Form factor
        form_factor = "ATX"
        if "MICRO-ATX" in title_upper or "MATX" in title_upper or "MICRO ATX" in title_upper:
            form_factor = "Micro-ATX"
        elif "MINI-ITX" in title_upper or "ITX" in title_upper:
            form_factor = "Mini-ITX"
        elif "E-ATX" in title_upper or "EATX" in title_upper:
            form_factor = "E-ATX"

        # Memory type
        memory_type = "DDR4" if "DDR4" in title_upper else "DDR5"

        # Product Line
        product_line = None
        for line in ["AORUS", "TUF GAMING", "ROG STRIX", "PRO", "PRIME", "STEEL LEGEND", "MORTAR", "TOMAHAWK"]:
            if line in title_upper:
                product_line = line.title()
                break

        return MotherboardSpecs(
            socket=socket,
            chipset=chipset,
            form_factor=form_factor,
            memory_type=memory_type,
            memory_slots=4,
            product_line=product_line,
        )

    @staticmethod
    def parse_ram(raw_title: str | None) -> RAMSpecs:
        title = raw_title or ""
        title_upper = title.upper()

        # Capacity
        cap_match = re.search(r"\b(\d{1,3})\s*GB\b", title_upper)
        capacity_gb = int(cap_match.group(1)) if cap_match else 32

        # Modules
        mod_match = re.search(r"(\d)\s*X\s*(\d{1,2})\s*GB", title_upper)
        module_count = int(mod_match.group(1)) if mod_match else 1

        # Memory type
        memory_type = "DDR4" if "DDR4" in title_upper else "DDR5"

        # Speed
        speed_match = re.search(r"\b(\d{4})\s*(?:MHZ|MT/S)?\b", title_upper)
        speed_mhz = int(speed_match.group(1)) if speed_match else (6000 if memory_type == "DDR5" else 3200)

        # Latency
        cl_match = re.search(r"\b(CL\d{2})\b", title_upper)
        latency_cl = cl_match.group(1) if cl_match else None

        # RGB
        has_rgb = "RGB" in title_upper

        return RAMSpecs(
            capacity_gb=capacity_gb,
            module_count=module_count,
            memory_type=memory_type,
            speed_mhz=speed_mhz,
            latency_cl=latency_cl,
            has_rgb=has_rgb,
        )
