import pytest
from src.core.title_parser import TitleParserRegistry


def test_gpu_parser_handles_none_and_empty():
    parsed_none = TitleParserRegistry.parse_gpu(None)
    assert parsed_none.chipset == "RTX 5070"
    assert parsed_none.vram_gb == 12
    assert parsed_none.is_oc is False

    parsed_empty = TitleParserRegistry.parse_gpu("")
    assert parsed_empty.chipset == "RTX 5070"


def test_gpu_parser_handles_noisy_and_unusual_titles():
    title = "   *** PLACA DE VÍDEO *** GALAX GEFORCE RTX 5070 TI 16GB GDDR7 256-BIT OC SFF DLSS RAYTRACING - 123456   "
    parsed = TitleParserRegistry.parse_gpu(title)

    assert parsed.brand_name == "Galax"
    assert parsed.chipset == "RTX 5070 TI"
    assert parsed.vram_gb == 16
    assert parsed.vram_type == "GDDR7"
    assert parsed.is_oc is True
    assert parsed.form_factor == "SFF"
    assert "DLSS" in parsed.features
    assert "Ray Tracing" in parsed.features


def test_motherboard_parser_edge_cases():
    title_ambiguous = "Placa Mae Generica sem informacao"
    mb = TitleParserRegistry.parse_motherboard(title_ambiguous)

    assert mb.socket in ["AM5", "AM4", "LGA1700"]
    assert mb.memory_type in ["DDR5", "DDR4"]


def test_ram_parser_edge_cases():
    title_noise = "Memoria RAM Gamer 32GB 6000MHz RGB"
    ram = TitleParserRegistry.parse_ram(title_noise)

    assert ram.capacity_gb == 32
    assert ram.speed_mhz == 6000
    assert ram.has_rgb is True
