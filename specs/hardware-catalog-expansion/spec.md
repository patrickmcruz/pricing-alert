# Initiative Spec: Hardware Catalog Expansion & Performance Hardening

**Status**: Living / In Progress  
**Initiative Slug**: `hardware-catalog-expansion`  
**Supercedes/Extends**: `specs/data-contract/spec.md` and `specs/system/spec.md`

---

## 1. Context & Motivation (WHY)

The initial system monitored a narrow set of GPUs using un-normalized product titles (e.g. `"Placa De Video Gigabyte NVIDIA Geforce RTX 5070 Ti Windforce Oc Sff 16gb Gddr7 Dlss Ray Tracing Gv N507twf3oc 16gd"`).

As the platform expands to support additional hardware categories (Placas Mãe, Memórias RAM, Processadores, SSDs) and scales to tens of thousands of price observations per day across multiple e-commerce stores:
1. **Catalog Integrity & Deduplication:** Stores publish the same physical hardware under varying title strings. Deduplicating products requires decomposing titles into explicit columns (`mpn`, `product_line`, `is_oc`) and category-specific `specs` (JSONB) linked to normalized `chipsets` foreign keys.
2. **Database Performance:** High-frequency writes with random `UUIDv4` primary keys cause severe B-Tree index fragmentation and disk I/O thrashing. Monolithic unpartitioned tables risk memory bloat during queries.
3. **Streamlit UI Scalability:** Un-cached `SELECT *` in-memory loading in Streamlit leads to Out-Of-Memory (OOM) crashes under large datasets.

---

## 2. Architectural Requirements (WHAT)

### A. Data Modeling & Catalog Normalization
- **Explicit Catalog Columns:** `products` table explicitly fields `mpn` (Manufacturer Part Number / SKU), `product_line` (e.g. 'Windforce', 'TUF'), and `is_oc` (boolean).
- **Normalized Foreign Keys:** `products` links to `chipsets` via explicit `chipset_id UUID REFERENCES chipsets(id)` foreign key.
- **Category Specs:** Extended attributes live in `products.specs` (JSONB) typed by category models (`GPUSpecs`, `MotherboardSpecs`, `RAMSpecs`).
- **GIN Indexing:** Index `products(specs)` using GIN (`idx_products_specs`) for high-performance JSONB querying.
- **View Projection:** `vw_dashboard_products` projects structured columns (`brand`, `model`, `mpn`, `product_line`, `is_oc`, `vram_gb`, `vram_type`, `chipset`, `form_factor`).

### B. Time-Series Storage & Performance
- **UUIDv7 Primary Keys:** Use time-ordered `UUIDv7` (RFC 9562) for `execution_id` and `price_observations.id` to ensure sequential B-Tree index writes.
- **Declarative Range Partitioning:** Convert `price_observations` to `PARTITION BY RANGE (scraped_at)` with monthly partitions.
- **SQL Pushdown & Streamlit Caching:** Streamlit `load_data()` uses `@st.cache_data(ttl=300)` and pushes time window filtering (`WHERE scraped_at >= NOW() - INTERVAL '60 days'`) down to PostgreSQL.

### C. Externalized Title Parsers & Safety
- **TitleParserRegistry:** Category-specific parsing (`parse_gpu`, `parse_motherboard`, `parse_ram`) backed by externalized TOML rules (`data/parsers/`).
- **Defensive Parsing:** Parsers return fallback defaults without raising unhandled runtime exceptions on malformed retailer titles.

---

## 3. Decisions Made & Rejected

- **Decision (Accepted):** Keep raw `product_title` on `listings` and `listing_runs` as immutable audit telemetry, while using normalized `products` for all application queries.
- **Decision (Accepted):** Use `UUIDv7` for time-series tables to combine the global uniqueness of UUIDs with sequential write performance of Auto-Increment IDs.
- **Decision (Rejected):** Storing all hardware attributes as flat database columns — rejected because every category (GPU vs RAM vs Motherboard) has different technical fields, which would create a sparse 100-column table. JSONB + GIN index is the chosen hybrid.
