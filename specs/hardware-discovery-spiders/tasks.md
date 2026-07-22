# Tasks: Pluggable Store Spiders Implementation Checklist

- [ ] **Task 1: Core Spider Contracts & Registry (`src/spiders/`)**
  - [ ] Create `src/spiders/base_spider.py` (`DiscoveredSKU`, `BaseSpider`)
  - [ ] Create `src/spiders/registry.py` (`@register_spider`, `get_registered_spiders`)
  - [ ] Create `src/spiders/__init__.py`

- [ ] **Task 2: CPU Specs & Title Parser Externalization**
  - [ ] Add `CPUSpecs` model in `src/core/specs.py`
  - [ ] Create `data/parsers/cpu.toml` parsing rules
  - [ ] Add `TitleParserRegistry.parse_cpu()` in `src/core/title_parser.py`

- [ ] **Task 3: Store Spider Implementations**
  - [ ] `src/spiders/mercadolivre.py` (`MercadoLivreSpider`)
  - [ ] `src/spiders/pichau.py` (`PichauSpider`)
  - [ ] `src/spiders/kabum.py` (`KabumSpider`)

- [ ] **Task 4: DiscoveryEngine Integration & Fast Verification**
  - [ ] Add `run_spider_discovery()` in `src/engine/discovery.py`
  - [ ] Create unit test suites `tests/unit/test_spiders.py` and `tests/unit/test_cpu_parser.py`
  - [ ] Fast terminal verification (1-2 SKUs test mode)
