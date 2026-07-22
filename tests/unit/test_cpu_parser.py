import unittest

from src.core.specs import CPUSpecs
from src.core.title_parser import TitleParserRegistry


class TestCPUParser(unittest.TestCase):

    def test_parse_ryzen_9800x3d(self):
        title = "Processador AMD Ryzen 7 9800X3D, 4.7GHz (5.2GHz Turbo), 8 Cores 16 Threads, AM5, Cache 96MB, 100-100001084WOF"
        specs = TitleParserRegistry.parse_cpu(title, search_keyword="ryzen 7 9800x3d")
        self.assertEqual(specs.manufacturer, "AMD")
        self.assertEqual(specs.socket, "AM5")
        self.assertEqual(specs.model_family, "Ryzen 7")
        self.assertEqual(specs.model_number, "9800X3D")
        self.assertTrue(specs.has_integrated_gpu)

    def test_parse_intel_core_14700k(self):
        title = "Processador Intel Core i7 14700K 3.4GHz (5.6GHz Turbo) 20-Cores 28-Threads LGA1700"
        specs = TitleParserRegistry.parse_cpu(title, search_keyword="core i7 14700k")
        self.assertEqual(specs.manufacturer, "Intel")
        self.assertEqual(specs.socket, "LGA1700")
        self.assertEqual(specs.model_family, "Core i7")
        self.assertEqual(specs.model_number, "14700K")
        self.assertTrue(specs.has_integrated_gpu)

    def test_parse_intel_core_ultra(self):
        title = "Processador Intel Core Ultra 7 265K 3.9GHz LGA 1851 Box"
        specs = TitleParserRegistry.parse_cpu(title, search_keyword="core ultra 7 265k")
        self.assertEqual(specs.manufacturer, "Intel")
        self.assertEqual(specs.socket, "LGA1851")
        self.assertTrue(specs.has_integrated_gpu)

    def test_parse_null_title_fallback(self):
        specs = TitleParserRegistry.parse_cpu(None)
        self.assertIsInstance(specs, CPUSpecs)
        self.assertEqual(specs.manufacturer, "Intel")


if __name__ == "__main__":
    unittest.main()
