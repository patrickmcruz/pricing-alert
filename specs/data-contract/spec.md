# Data Contract Spec

Supersedes `.gemini/.artifacts/artifact3-data_contract.md` (historical — missing `parser_version`, `brand`/`model`, `discount`, `installment_count`, `produto_id`, and the whole catalog/DB layer; kept for archaeology, not accuracy).

**Source of truth**: `src/core/contract.py` (Pydantic contracts) and `src/db/schema.py` (Postgres DDL). This spec explains the *why* behind their shape; if it and the code ever disagree, the code is right and this doc is stale — fix the doc.

## 1. `PriceContract` (`src/core/contract.py`)

Canonical representation of one scraped price observation. Every scraper's `parse()` must return one (or `None`).

- `model_config = ConfigDict(frozen=True, extra="forbid", validate_assignment=True)` — immutable, and any unexpected field is a hard error rather than a silent drop. This is intentional: a scraper accidentally passing a field that doesn't exist on the contract should fail loudly in tests, not ship silently.
- `execution_id: UUID` — unique per observation; becomes `price_observations.id` at persistence time (`PostgresPriceRepository.save_prices`). Traceability end-to-end: a dashboard row, a log line, and a DB row all key off this.
- `price_cash` / `price_installments`: `Decimal`, never `float` — monetary values must not carry floating-point rounding error.
- `produto_id: str | None` — FK into the catalog's `products` table (see §2). Nullable because historical rows predate the catalog's existence and because a scraper that hasn't resolved a catalog entry yet still needs to persist *something*; `DiscoveryEngine._backfill_existing_rows` reconciles these after the fact.
- `discount`, `installment_count`, `brand`, `model`, `parser_version` were added after the original artifact — `parser_version` specifically exists so a selector-drift incident (`SelectorOutdatedException`) can be traced to exactly which selector version was live when a page stopped parsing correctly.

## 2. Catalog (`src/core/catalog.py`)

`Categoria`/`Marca`/`Produto`/`ResolvedProduto` — the normalized product catalog `PriceContract`/`ProductSKU` reference by id instead of carrying free-text brand/model strings. Deliberately generalized beyond GPUs: `Categoria` is any product category ("GPU", "Notebook", ...), and category-specific attributes (chipset, VRAM, RAM...) live in `Produto.specs` (a JSONB dict) rather than as dedicated columns — adding a new category never requires a schema migration.

**Naming note**: these Pydantic class/field names (`Categoria`, `nome`, `marca_id`) stayed Portuguese even after the underlying Postgres tables were renamed to English (`categories`, `name`, `brand_id`) — see `specs/system/spec.md` §7. This is a deliberate, scoped decision: the database schema is what a future SQL query or migration touches directly and where Portuguese/English mixing was actively confusing; the Python model layer maps between the two either way (repositories translate `nome` ↔ `name` by hand), and renaming *every* Python identifier was judged out of scope for that change. If this mismatch becomes its own source of confusion, renaming the Python layer to match is a valid follow-up — but should get its own spec, not be folded silently into an unrelated change.

`GPU_CATEGORY_SLUG = "gpu"` is the one hardcoded category slug every current scraper/discovery flow resolves into. A new category (e.g. this project's first non-GPU integration) needs no code change to the catalog itself — just a new slug constant and a `DiscoveryEngine`/scraper wired to use it.

## 3. `ProductSKU` (`src/core/contract.py`)

A discovered, trackable listing: `store_name` + `product_url` + `produto_id` (+ `brand`/`model`, populated at *read* time by the repository via a JOIN, never hand-set). Persisted as a `listings` row (soft-deleted via `is_active`, never hard-deleted, so `price_observations` history is never orphaned by FK).

## 4. `StoreConfig` (`src/core/contract.py`)

Per-store scheduling configuration (`cron_times`, `enabled`). If `enabled: true` but no scraper is registered for that `store_name`, `PriceEngine.build_schedule()` raises `MissingScraperError` at startup — a deliberate hard failure over a silent skip, so a typo in `data/target-stores-list.json` is caught immediately instead of silently never scheduling a store.

## 5. Alerting contracts (`src/alerts/contracts.py`)

Not in the original artifact at all — the alerting domain (`AlertRule`, `AlertEvent`, `ThresholdType`) was added afterward. `AlertRule.matches()` is pure (no I/O), so it's fixture-testable the same way scraper `parse()` methods are. `AlertEvaluator` takes the previous known price as an explicit argument rather than fetching history itself, for the same reason.

## 6. Database schema (`src/db/schema.py`)

See `README.md`'s "Database Schema" section for the current table list — not duplicated here to avoid a second place to keep in sync. The short version: every table/column name is English (`stores`, `products`, `listings`, `price_observations`, ...), every primary key is a Postgres `UUID`, and every foreign key is enforced natively (not merely declared) — Postgres does this by default, unlike SQLite where it required `PRAGMA foreign_keys = ON` per connection.
