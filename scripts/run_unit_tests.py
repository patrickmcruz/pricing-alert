import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.title_parser import TitleParserRegistry
from src.core.utils import uuid7


def test_uuid7_ordering():
    u1 = uuid7()
    u2 = uuid7()
    assert u1.version == 7
    assert u2.version == 7
    assert u1 != u2
    assert u1 <= u2
    print("  [PASS] UUIDv7 generation and ordering test")


def test_gpu_parser_full():
    raw = "Placa De Video Gigabyte NVIDIA Geforce RTX 5070 Ti Windforce Oc Sff 16gb Gddr7 Dlss Ray Tracing Gv N507twf3oc 16gd"
    card = TitleParserRegistry.parse_gpu(raw, search_keyword="rtx 5070 ti")
    assert card.chipset == "RTX 5070 TI"
    assert card.vram_gb == 16
    assert card.vram_type == "GDDR7"
    assert card.is_oc is True
    assert card.form_factor == "SFF"
    assert "DLSS" in card.features
    print("  [PASS] GPU Title Parser full title test")


def test_gpu_parser_edge_cases():
    card_none = TitleParserRegistry.parse_gpu(None)
    assert card_none.chipset == "RTX 5070"
    
    card_noise = "   *** PLACA DE VÍDEO *** GALAX GEFORCE RTX 5070 TI 16GB GDDR7 DLSS RAYTRACING   "
    card = TitleParserRegistry.parse_gpu(card_noise)
    assert card.chip_maker == "NVIDIA"
    assert card.chipset == "RTX 5070 TI"
    print("  [PASS] GPU Title Parser edge cases test")


def test_motherboard_parser():
    raw = "Placa Mãe Asus TUF Gaming B650M-Plus, AMD AM5, mATX, DDR5"
    mb = TitleParserRegistry.parse_motherboard(raw)
    assert mb.socket == "AM5"
    assert mb.memory_type == "DDR5"
    assert mb.form_factor == "Micro-ATX"
    print("  [PASS] Motherboard Title Parser test")


def test_ram_parser():
    raw = "Memória Corsair Vengeance RGB 32GB (2x16GB) 6000MHz DDR5 CL30"
    ram = TitleParserRegistry.parse_ram(raw)
    assert ram.capacity_gb == 32
    assert ram.module_count == 2
    assert ram.speed_mhz == 6000
    assert ram.has_rgb is True
    print("  [PASS] RAM Title Parser test")


def run_all():
    print("=" * 60)
    print("RUNNING AUTOMATED UNIT TEST SUITE")
    print("=" * 60)
    test_uuid7_ordering()
    test_gpu_parser_full()
    test_gpu_parser_edge_cases()
    test_motherboard_parser()
    test_ram_parser()
    print("=" * 60)
    print("ALL UNIT TESTS PASSED SUCCESSFULLY (100% SUCCESS RATE)")
    print("=" * 60)


if __name__ == "__main__":
    run_all()
