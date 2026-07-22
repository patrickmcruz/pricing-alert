# Task Checklist: Hardware Catalog Expansion & Performance Hardening

**Initiative**: `hardware-catalog-expansion`  
**Branch**: `refactor/db-architecture-performance-hardening`

---

- [x] **Block 1: Branching & Base Foundation Commit**
  - [x] Create branch `refactor/db-architecture-performance-hardening` from `develop`
  - [x] Commit initial Pydantic specs (`src/core/specs.py`), Title Parser (`src/core/title_parser.py`), and DDL updates
  - [x] **Commit**: `feat(catalog): add structured specs and title parser engine` (`3b215b6`)

- [x] **Block 2: Streamlit UI Pushdown SQL & Caching**
  - [x] Add `@st.cache_data(ttl=300)` to `load_data()` in `src/ui/Dashboard.py`
  - [x] Push down date range filter (`WHERE scraped_at >= NOW() - INTERVAL '60 days'`) into SQL
  - [x] **Commit**: `perf(ui): implement sql pushdown filtering and streamlit caching` (`1e9122c`)

- [x] **Block 3: MPN Deduplication & `chipset_id` Foreign Key**
  - [x] Add `chipset_id UUID REFERENCES chipsets(id)` to `products` in `src/db/schema.py`
  - [x] Update `Produto` model in `src/core/catalog.py`
  - [x] Execute DDL migration on PostgreSQL `pricing_db`
  - [x] **Commit**: `refactor(db): enforce chipset_id foreign key and mpn-based deduplication` (`eb35266`)

- [x] **Block 4: Time-Series Storage Optimization (UUIDv7)**
  - [x] Implement `uuid7()` generator in `src/core/utils.py`
  - [x] Adopt `uuid7()` for `PriceContract.execution_id` in `src/core/contract.py`
  - [x] Unit tests for UUIDv7 generation & B-tree order
  - [x] **Commit**: `perf(db): adopt time-ordered uuidv7 for price_observations primary keys` (`0629c48`)

- [x] **Block 5: Declarative Range Partitioning for `price_observations`**
  - [x] Update `src/db/schema.py` DDL with `PARTITION BY RANGE (scraped_at)`
  - [x] Implement monthly partition provisioner
  - [x] Verify query routing & writes on PostgreSQL
  - [x] **Commit**: `feat(db): implement declarative range partitioning by month for price_observations` (`cfc057e`)

- [x] **Block 6: Externalized TOML Parser Rules & Null Safety**
  - [x] Create `data/parsers/gpu.toml`, `data/parsers/motherboard.toml`, `data/parsers/ram.toml`
  - [x] Update `TitleParserRegistry` to load TOML configs
  - [x] Unit tests & defensive parsing checks
  - [x] **Commit**: `refactor(parser): externalize title parsing rules to toml configurations` (`afbcf3a`)

- [x] **Block 7: Documentation & MER/DER Synchronization**
  - [x] Update `specs/README.md`, `specs/data-contract/spec.md`, and `docs/database/DER_MER.md`
  - [x] Verify all markdown links and diagrams
  - [x] **Commit**: `docs: update MER/DER diagrams and architecture specs for partitioned schema`
