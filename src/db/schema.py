from __future__ import annotations

from contextlib import asynccontextmanager

import aiosqlite

_DDL = [
    """CREATE TABLE IF NOT EXISTS stores (
        id TEXT PRIMARY KEY,
        slug TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL,
        base_url TEXT,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        created_at TIMESTAMP NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS brands (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS chipsets (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        chip_maker TEXT NOT NULL CHECK (chip_maker IN ('NVIDIA','AMD','UNKNOWN')),
        created_at TIMESTAMP NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS gpu_models (
        id TEXT PRIMARY KEY,
        brand_id TEXT NOT NULL REFERENCES brands(id),
        chipset_id TEXT NOT NULL REFERENCES chipsets(id),
        model_name TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        UNIQUE(brand_id, chipset_id, model_name)
    )""",
    """CREATE TABLE IF NOT EXISTS store_listings (
        id TEXT PRIMARY KEY,
        store_id TEXT NOT NULL REFERENCES stores(id),
        gpu_model_id TEXT NOT NULL REFERENCES gpu_models(id),
        product_url TEXT NOT NULL UNIQUE,
        product_title TEXT NOT NULL,
        search_keyword TEXT NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS scraper_runs (
        id TEXT PRIMARY KEY,
        store_id TEXT NOT NULL REFERENCES stores(id),
        status TEXT NOT NULL,
        started_at TIMESTAMP NOT NULL,
        finished_at TIMESTAMP,
        listings_total INTEGER NOT NULL DEFAULT 0,
        listings_succeeded INTEGER NOT NULL DEFAULT 0,
        listings_failed INTEGER NOT NULL DEFAULT 0,
        error_message TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS listing_runs (
        id TEXT PRIMARY KEY,
        scraper_run_id TEXT NOT NULL REFERENCES scraper_runs(id),
        store_listing_id TEXT REFERENCES store_listings(id),
        product_url TEXT NOT NULL,
        product_title TEXT NOT NULL,
        status TEXT NOT NULL,
        started_at TIMESTAMP NOT NULL,
        finished_at TIMESTAMP,
        error_message TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS price_observations (
        id TEXT PRIMARY KEY,
        store_listing_id TEXT NOT NULL REFERENCES store_listings(id),
        scraper_run_id TEXT REFERENCES scraper_runs(id),
        price_cash DECIMAL(10,2) NOT NULL,
        price_installments DECIMAL(10,2),
        installment_count INTEGER,
        currency TEXT NOT NULL,
        discount DECIMAL(10,2),
        is_available BOOLEAN NOT NULL,
        parser_version TEXT NOT NULL,
        scraped_at TIMESTAMP NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS trigger_requests (
        id TEXT PRIMARY KEY,
        store_id TEXT REFERENCES stores(id),
        status TEXT NOT NULL,
        requested_at TIMESTAMP NOT NULL,
        processed_at TIMESTAMP,
        error_message TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS alert_rules (
        id TEXT PRIMARY KEY,
        store_id TEXT REFERENCES stores(id),
        gpu_model_id TEXT REFERENCES gpu_models(id),
        search_keyword TEXT,
        threshold_type TEXT NOT NULL,
        threshold_value DECIMAL(10,2),
        is_active BOOLEAN NOT NULL,
        created_at TIMESTAMP NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS alert_events (
        id TEXT PRIMARY KEY,
        alert_rule_id TEXT NOT NULL REFERENCES alert_rules(id),
        price_observation_id TEXT NOT NULL REFERENCES price_observations(id),
        reason TEXT NOT NULL,
        triggered_at TIMESTAMP NOT NULL
    )""",
]

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_scraper_runs_store ON scraper_runs(store_id)",
    "CREATE INDEX IF NOT EXISTS idx_scraper_runs_started_at ON scraper_runs(started_at)",
    "CREATE INDEX IF NOT EXISTS idx_listing_runs_scraper_run ON listing_runs(scraper_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_listing_runs_listing ON listing_runs(store_listing_id)",
    "CREATE INDEX IF NOT EXISTS idx_price_observations_listing ON price_observations(store_listing_id, scraped_at)",
    "CREATE INDEX IF NOT EXISTS idx_price_observations_run ON price_observations(scraper_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_trigger_requests_status ON trigger_requests(status)",
    "CREATE INDEX IF NOT EXISTS idx_alert_rules_active ON alert_rules(is_active)",
    "CREATE INDEX IF NOT EXISTS idx_alert_events_rule ON alert_events(alert_rule_id)",
    "CREATE INDEX IF NOT EXISTS idx_store_listings_store ON store_listings(store_id)",
]


@asynccontextmanager
async def connect(db_path: str):
    """Every repository should use this instead of raw aiosqlite.connect - it
    turns on FK enforcement (off by default in SQLite) on every connection."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        yield db


async def initialize_schema(db_path: str) -> None:
    """Single source of truth for the schema. Call once at boot (main.py) and
    from anywhere else that needs a guaranteed-initialized DB (Streamlit pages,
    scripts) - CREATE TABLE IF NOT EXISTS is idempotent."""
    async with connect(db_path) as db:
        for stmt in _DDL:
            await db.execute(stmt)
        for stmt in _INDEXES:
            await db.execute(stmt)
        await db.commit()
