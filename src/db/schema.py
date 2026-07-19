from __future__ import annotations

import json
from contextlib import asynccontextmanager

import asyncpg

_DDL = [
    """CREATE TABLE IF NOT EXISTS categories (
        id          UUID PRIMARY KEY,
        name        TEXT NOT NULL,
        slug        TEXT NOT NULL UNIQUE,
        parent_id   UUID REFERENCES categories(id),
        created_at  TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS brands (
        id          UUID PRIMARY KEY,
        name        TEXT NOT NULL UNIQUE,
        created_at  TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS products (
        id            UUID PRIMARY KEY,
        brand_id      UUID NOT NULL REFERENCES brands(id),
        category_id   UUID NOT NULL REFERENCES categories(id),
        name          TEXT NOT NULL,
        gtin          TEXT UNIQUE,
        specs         JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at    TIMESTAMPTZ NOT NULL
    )""",
    # Expression index instead of a plain UNIQUE constraint, since the
    # identity key includes a JSONB field (specs->>'chipset') - lets two
    # products differ only by chipset (e.g. same brand/name, different chip).
    """CREATE UNIQUE INDEX IF NOT EXISTS idx_products_identity
        ON products (brand_id, category_id, LOWER(name), (specs->>'chipset'))""",
    """CREATE TABLE IF NOT EXISTS stores (
        id            UUID PRIMARY KEY,
        slug          TEXT NOT NULL UNIQUE,
        display_name  TEXT NOT NULL,
        base_url      TEXT,
        is_active     BOOLEAN NOT NULL DEFAULT true,
        created_at    TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS listings (
        id             UUID PRIMARY KEY,
        store_id       UUID NOT NULL REFERENCES stores(id),
        product_id     UUID NOT NULL REFERENCES products(id),
        product_url    TEXT NOT NULL UNIQUE,
        product_title  TEXT NOT NULL,
        search_keyword TEXT NOT NULL,
        is_active      BOOLEAN NOT NULL DEFAULT true,
        created_at     TIMESTAMPTZ NOT NULL,
        updated_at     TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS scraper_runs (
        id                  UUID PRIMARY KEY,
        store_id            UUID NOT NULL REFERENCES stores(id),
        status              TEXT NOT NULL,
        started_at          TIMESTAMPTZ NOT NULL,
        finished_at         TIMESTAMPTZ,
        listings_total      INTEGER NOT NULL DEFAULT 0,
        listings_succeeded  INTEGER NOT NULL DEFAULT 0,
        listings_failed     INTEGER NOT NULL DEFAULT 0,
        error_message       TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS listing_runs (
        id              UUID PRIMARY KEY,
        scraper_run_id  UUID NOT NULL REFERENCES scraper_runs(id),
        listing_id      UUID REFERENCES listings(id),
        product_url     TEXT NOT NULL,
        product_title   TEXT NOT NULL,
        status          TEXT NOT NULL,
        started_at      TIMESTAMPTZ NOT NULL,
        finished_at     TIMESTAMPTZ,
        error_message   TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS price_observations (
        id                     UUID PRIMARY KEY,
        listing_id             UUID NOT NULL REFERENCES listings(id),
        scraper_run_id         UUID REFERENCES scraper_runs(id),
        price_cash             NUMERIC(12,2) NOT NULL,
        price_installments     NUMERIC(12,2),
        installment_count      INTEGER,
        currency               TEXT NOT NULL,
        discount                NUMERIC(12,2),
        is_available           BOOLEAN NOT NULL,
        parser_version         TEXT NOT NULL,
        scraped_at             TIMESTAMPTZ NOT NULL
    )""",
    # Raw manifest of record for DiscoveryEngine, replacing data/target_urls.json
    # (see specs/target-urls-table/spec.md) - deliberately a plain, denormalized
    # staging table, not FK'd into products/brands: it holds whatever a human or
    # a discovery script *proposed* tracking, in free-text form, before
    # DiscoveryEngine._resolve_catalog() turns it into a real Produto. Keeping it
    # separate from `listings` (which holds the *resolved* record) preserves that
    # distinction instead of blurring it.
    """CREATE TABLE IF NOT EXISTS target_urls (
        id             UUID PRIMARY KEY,
        store_name     TEXT NOT NULL,
        search_keyword TEXT NOT NULL,
        product_url    TEXT NOT NULL UNIQUE,
        brand          TEXT,
        model          TEXT,
        product_title  TEXT,
        created_at     TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS trigger_requests (
        id            UUID PRIMARY KEY,
        store_id      UUID REFERENCES stores(id),
        status        TEXT NOT NULL,
        requested_at  TIMESTAMPTZ NOT NULL,
        processed_at  TIMESTAMPTZ,
        error_message TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS alert_rules (
        id              UUID PRIMARY KEY,
        store_id        UUID REFERENCES stores(id),
        product_id      UUID REFERENCES products(id),
        search_keyword  TEXT,
        threshold_type  TEXT NOT NULL,
        threshold_value NUMERIC(12,2),
        is_active       BOOLEAN NOT NULL,
        created_at      TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS alert_events (
        id                      BIGSERIAL PRIMARY KEY,
        alert_rule_id           UUID NOT NULL REFERENCES alert_rules(id),
        price_observation_id    UUID NOT NULL REFERENCES price_observations(id),
        reason                  TEXT NOT NULL,
        triggered_at            TIMESTAMPTZ NOT NULL
    )""",
]

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_scraper_runs_store ON scraper_runs(store_id)",
    "CREATE INDEX IF NOT EXISTS idx_scraper_runs_started_at ON scraper_runs(started_at)",
    "CREATE INDEX IF NOT EXISTS idx_listing_runs_scraper_run ON listing_runs(scraper_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_listing_runs_listing ON listing_runs(listing_id)",
    "CREATE INDEX IF NOT EXISTS idx_price_observations_listing ON price_observations(listing_id, scraped_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_price_observations_run ON price_observations(scraper_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_trigger_requests_status ON trigger_requests(status)",
    "CREATE INDEX IF NOT EXISTS idx_alert_rules_active ON alert_rules(is_active)",
    "CREATE INDEX IF NOT EXISTS idx_alert_events_rule ON alert_events(alert_rule_id)",
    "CREATE INDEX IF NOT EXISTS idx_listings_store ON listings(store_id)",
    "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id)",
    "CREATE INDEX IF NOT EXISTS idx_target_urls_store ON target_urls(store_name)",
]


def affected_rows(status: str) -> int:
    """Parses the row count out of asyncpg's execute() status string, e.g.
    "UPDATE 3" -> 3. asyncpg has no cursor.rowcount equivalent - the command
    tag is the only place this number comes back."""
    return int(status.rsplit(" ", 1)[-1])


@asynccontextmanager
async def connect(dsn: str):
    """Every repository should use this instead of raw asyncpg.connect - single
    place to add pooling later without touching every call site. Registers a
    jsonb codec so products.specs round-trips as a plain Python dict instead of
    a str every caller would have to json.loads() themselves."""
    conn = await asyncpg.connect(dsn)
    try:
        await conn.set_type_codec(
            "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
        )
        yield conn
    finally:
        await conn.close()


async def initialize_schema(dsn: str) -> None:
    """Single source of truth for the schema. Call once at boot (main.py) and
    from anywhere else that needs a guaranteed-initialized DB (Streamlit pages,
    scripts) - CREATE TABLE/INDEX IF NOT EXISTS is idempotent."""
    async with connect(dsn) as db:
        for stmt in _DDL:
            await db.execute(stmt)
        for stmt in _INDEXES:
            await db.execute(stmt)
