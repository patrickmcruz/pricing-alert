# `target_urls` Database Table Plan

Implements `spec.md`. Follows the existing repository-pattern precedent (`CatalogRepository`/`PostgresCatalogRepository`) exactly.

## Files

| File | Change |
|---|---|
| `src/db/schema.py` | New `target_urls` table DDL + an index on `store_name`. |
| `src/core/contract.py` | New `TargetUrlEntry` model — the row shape for this table (distinct from `LegacyTargetUrlRow`, which is a different, already-existing concept: a `listings` row missing its `produto_id`, not a pre-catalog manifest entry). |
| `src/repositories/target_url_repository.py` | New abstract `TargetUrlRepository`: `list_all()`, `upsert_many()`. |
| `src/repositories/postgres_target_url_repository.py` | Postgres implementation. |
| `src/engine/discovery.py` | `DiscoveryEngine` takes a `target_url_repository: TargetUrlRepository` instead of `target_urls_path: str`; `run_discovery()` calls `list_all()` instead of opening a file. |
| `main.py` | Wires `PostgresTargetUrlRepository(dsn=settings.db_dsn)` into the `DiscoveryEngine` construction. |
| `scripts/migrate_target_urls.py` | Rewritten: one-time import of `data/target_urls.json` (if it still exists locally) into the new table via `upsert_many()`, then runs `DiscoveryEngine.run_discovery()` as before (now DB-driven) to resolve the catalog. |
| `scripts/discover_pichau_gpus.py` | Writes new candidates via `PostgresTargetUrlRepository.upsert_many()` instead of read-modify-writing `data/target_urls.json`. |
| `tests/unit/test_discovery.py` | Rewritten against a fake in-memory `TargetUrlRepository` instead of a temp JSON file. |
| `tests/unit/test_postgres_target_url_repository.py` | New — same shape as the existing `test_postgres_catalog_repository.py`, run against the real local Postgres (`pricing_db`), following this repo's existing "test against the real thing" convention for Postgres repositories. |
| `data/target_urls.json` | Deleted once the one-time migration has run and been verified — see spec §2, this is a one-way cutover. |

## `target_urls` table

```sql
CREATE TABLE IF NOT EXISTS target_urls (
    id             UUID PRIMARY KEY,
    store_name     TEXT NOT NULL,
    search_keyword TEXT NOT NULL,
    product_url    TEXT NOT NULL UNIQUE,
    brand          TEXT,
    model          TEXT,
    product_title  TEXT,
    created_at     TIMESTAMPTZ NOT NULL
)
```

`UNIQUE(product_url)` is what makes `upsert_many()`'s `ON CONFLICT (product_url) DO NOTHING` an idempotent, concurrency-safe insert — the same idempotency contract the old JSON-based scripts maintained by hand (checking `existing_urls` before appending).

## `TargetUrlRepository` design

```python
class TargetUrlRepository(ABC):
    async def list_all(self) -> list[TargetUrlEntry]: ...
    async def upsert_many(self, entries: list[TargetUrlEntry]) -> int:
        """Inserts new rows; existing product_urls are left untouched. Returns the count actually inserted."""
```

`PostgresTargetUrlRepository.upsert_many()` inserts one row at a time in a loop (matching `PostgresCatalogRepository`'s per-call-`connect()` style rather than introducing a new bulk-insert helper) and sums `affected_rows()` (`src/db/schema.py`, already used elsewhere) across each `ON CONFLICT DO NOTHING` execute to report how many were genuinely new.

## `DiscoveryEngine` change

`run_discovery()`'s file-reading block:

```python
if not os.path.exists(self.target_urls_path): ...
with open(self.target_urls_path) as f: data = json.load(f)
for item in data: ...
```

becomes:

```python
entries = await self.target_url_repository.list_all()
if not entries:
    logger.warning("No rows in target_urls. Skipping discovery.")
    return
for entry in entries: ...
```

Everything downstream (`_resolve_catalog`, building `ProductSKU`, `repository.save_skus`) is unchanged — only the source of the loop's items changes from parsed JSON dicts to `TargetUrlEntry` objects (same field names, so the loop body barely changes).

## `scripts/discover_pichau_gpus.py` change

Replaces `_load_existing_manifest()`/the final `json.dump()` block with:

```python
target_url_repo = PostgresTargetUrlRepository(dsn=settings.db_dsn)
existing = await target_url_repo.list_all()
existing_urls = {e.product_url for e in existing}
...
new_entries = [TargetUrlEntry(**row) for row in new_rows]
inserted = await target_url_repo.upsert_many(new_entries)
```

`await initialize_schema(settings.db_dsn)` added at the top of `discover()`, matching `scripts/migrate_target_urls.py`'s and `scripts/run_all_scrapers.py`'s existing pattern for standalone scripts that touch the DB directly.

## Verification

1. `pytest tests/unit/test_discovery.py tests/unit/test_postgres_target_url_repository.py -v`.
2. Run `python scripts/migrate_target_urls.py` for real against the local `pricing_db` Postgres instance (already running via docker-compose) — confirms the table gets created, every existing `data/target_urls.json` row (including the 72 Pichau ones) lands in it, and the catalog/listings resolution step still runs correctly afterward.
3. Confirm row counts: `SELECT store_name, COUNT(*) FROM target_urls GROUP BY store_name` should match `data/target_urls.json`'s per-store counts before it's deleted.
4. Full `pytest -q` run to confirm nothing else broke.
5. Delete `data/target_urls.json` only after 2-4 pass.
