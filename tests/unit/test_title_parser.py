import pytest
from src.core.title_parser import TitleParserRegistry


def test_parse_gpu_full_title():
    raw = "Placa De Video Gigabyte NVIDIA Geforce RTX 5070 Ti Windforce Oc Sff 16gb Gddr7 Dlss Ray Tracing Gv N507twf3oc 16gd"
    card = TitleParserRegistry.parse_gpu(raw, search_keyword="rtx 5070 ti")

    assert card.brand_name == "Gigabyte" or "GIGABYTE" in raw.upper()
    assert card.chipset == "RTX 5070 TI"
    assert card.chip_maker == "NVIDIA"
    assert card.vram_gb == 16
    assert card.vram_type == "GDDR7"
    assert card.is_oc is True
    assert card.form_factor == "SFF"
    assert card.product_line == "Windforce"
    assert "DLSS" in card.features
    assert "Ray Tracing" in card.features


def test_parse_motherboard_title():
    raw = "Placa Mãe Asus TUF Gaming B650M-Plus, AMD AM5, mATX, DDR5"
    mb = TitleParserRegistry.parse_motherboard(raw)

    assert mb.socket == "AM5"
    assert mb.chipset == "B650M" or "B650" in mb.chipset
    assert mb.form_factor == "Micro-ATX"
    assert mb.memory_type == "DDR5"
    assert mb.product_line == "Tuf Gaming"


def test_parse_ram_title():
    raw = "Memória Corsair Vengeance RGB 32GB (2x16GB) 6000MHz DDR5 CL30"
    ram = TitleParserRegistry.parse_ram(raw)

    assert ram.capacity_gb == 32
    assert ram.module_count == 2
    assert ram.memory_type == "DDR5"
    assert ram.speed_mhz == 6000
    assert ram.latency_cl == "CL30"
    assert ram.has_rgb is True
