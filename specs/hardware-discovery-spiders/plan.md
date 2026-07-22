# Implementation Plan: Pluggable Store Spiders Architecture

## Phases

### Phase 1: Core Spider Contracts & Registry
- Create `DiscoveredSKU` contract and `BaseSpider` ABC in `src/spiders/base_spider.py`.
- Create `@register_spider` decorator in `src/spiders/registry.py`.

### Phase 2: CPU Specs & Parser Externalization
- Add `CPUSpecs` in `src/core/specs.py`.
- Create `data/parsers/cpu.toml` with regex parsing rules for AMD Ryzen and Intel Core/Ultra.
- Add `TitleParserRegistry.parse_cpu()` in `src/core/title_parser.py`.

### Phase 3: Store Spider Implementations
- `MercadoLivreSpider`: REST search API integration (`/sites/MLB/search`).
- `PichauSpider`: GraphQL / RSC embedded JSON search grid extraction.
- `KabumSpider`: Playwright search extraction.

### Phase 4: DiscoveryEngine Integration
- Add `run_spider_discovery()` in `src/engine/discovery.py`.
- Idempotent upsert into PostgreSQL tables.

### Phase 5: Automated Testing & Fast Verification
- Add unit tests in `tests/unit/test_spiders.py` and `tests/unit/test_cpu_parser.py`.
- Execute fast terminal verification with 1-2 test keywords.
