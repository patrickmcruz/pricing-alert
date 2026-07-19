# `target_urls` Database Table Spec

## 1. What & Why

Replace `data/target_urls.json` — a git-tracked flat file that both humans (hand-editing) and code (`scripts/discover_pichau_gpus.py`) write rows into — with a dedicated `target_urls` Postgres table as the actual manifest of record.

The JSON file has real problems once more than one thing writes to it: `scripts/discover_pichau_gpus.py` read-modify-writes the whole file, so two discovery runs (or a discovery run racing a hand-edit) can clobber each other; there's no created-at audit trail for when a row was added; and it requires the file to be mounted/shipped into every container that runs `DiscoveryEngine` rather than just being data already in the database everything else already lives in. A table gets safe concurrent upserts (`UNIQUE(product_url)` + `ON CONFLICT DO NOTHING`), an audit timestamp, and puts this data next to the rest of the schema (`src/db/schema.py`) instead of a side-channel file.

## 2. Requirements

- A new `target_urls` table: `store_name`, `search_keyword`, `product_url` (unique), `brand`, `model`, `product_title`, `created_at`. Deliberately a **plain, denormalized staging table** — see §3 for why this stays separate from the `products`/`brands`/`categories` catalog.
- `DiscoveryEngine` (`src/engine/discovery.py`) reads its raw input from this table instead of opening `data/target_urls.json` — no other behavior changes: it still resolves/creates the `Categoria`/`Marca`/`Produto` catalog entries and upserts `listings` rows exactly as before (see `specs/data-contract/spec.md` §2).
- `scripts/discover_pichau_gpus.py` (and any future discovery script) writes new candidates directly into this table instead of read-modify-writing the JSON file.
- One-time migration: `data/target_urls.json`'s existing rows (every store, including the 72 Pichau rows discovered in the previous initiative) get imported into the table, then the JSON file is retired — this is a genuine one-way cutover, not a dual-write scheme; keeping both around as two "sources of truth" would just recreate the same drift problem in a different shape.

## 3. Architecture decision: a separate staging table, not new columns on `listings`

Two ways to store this:

**(a) A new `target_urls` table**, holding exactly the free-text fields the JSON file held, with `DiscoveryEngine` doing the same resolve-into-catalog step it already does, just reading from here instead of a file.

**(b) Extend `listings`** with the free-text `brand`/`model` fields directly, and have discovery scripts write straight into `listings`/`products`/`brands`, skipping the intermediate representation entirely.

**Decision: (a).** `listings` rows are *resolved* records — they carry a `product_id` FK into the catalog, and a scraper/dashboard/alert consuming a `listings` row should never need to care whether "Zotac" was typed by a human or scraped from `marcas_info.name`. Collapsing "what a discovery script proposed tracking" into the same table as "what the catalog has resolved and is actively scraping" would blur that line — the same reason `ProductSKU.brand`/`.model` are already documented as populated by the repository at read time, never hand-set (`src/core/contract.py`). Keeping `target_urls` as a separate, deliberately dumb staging table means `DiscoveryEngine._resolve_catalog()` remains the *only* place free-text brand/model becomes a real `Produto` — nothing about that resolution logic changes in this initiative, only where its raw input comes from.

## 4. Non-goals

- No dashboard/UI page for managing `target_urls` rows directly (the existing "Gerenciar GPUs" page already manages the resolved catalog; this table is upstream of that, edited by discovery scripts or direct SQL, not a new UI surface).
- No change to `data/target-stores-list.json` or its `enabled` flag — that still controls per-store *scheduling*, a separate concern from *which URLs* get tracked.
- No change to how `listings`/`products`/`price_observations` work, and no backfill/reshaping of historical data — this only touches the pre-catalog input stage.
