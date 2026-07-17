from __future__ import annotations

import json
from contextlib import asynccontextmanager

import asyncpg

_DDL = [
    """CREATE TABLE IF NOT EXISTS categoria (
        id          UUID PRIMARY KEY,
        nome        TEXT NOT NULL,
        slug        TEXT NOT NULL UNIQUE,
        parent_id   UUID REFERENCES categoria(id),
        criado_em   TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS marca (
        id          UUID PRIMARY KEY,
        nome        TEXT NOT NULL UNIQUE,
        criado_em   TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS produto (
        id            UUID PRIMARY KEY,
        marca_id      UUID NOT NULL REFERENCES marca(id),
        categoria_id  UUID NOT NULL REFERENCES categoria(id),
        nome          TEXT NOT NULL,
        gtin          TEXT UNIQUE,
        specs         JSONB NOT NULL DEFAULT '{}'::jsonb,
        criado_em     TIMESTAMPTZ NOT NULL
    )""",
    # Expression index instead of a plain UNIQUE constraint, since the
    # identity key includes a JSONB field (specs->>'chipset') - lets two
    # products differ only by chipset (e.g. same brand/name, different chip).
    """CREATE UNIQUE INDEX IF NOT EXISTS idx_produto_identity
        ON produto (marca_id, categoria_id, LOWER(nome), (specs->>'chipset'))""",
    """CREATE TABLE IF NOT EXISTS loja (
        id            UUID PRIMARY KEY,
        slug          TEXT NOT NULL UNIQUE,
        display_name  TEXT NOT NULL,
        base_url      TEXT,
        is_active     BOOLEAN NOT NULL DEFAULT true,
        created_at    TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS anuncio (
        id             UUID PRIMARY KEY,
        loja_id        UUID NOT NULL REFERENCES loja(id),
        produto_id     UUID NOT NULL REFERENCES produto(id),
        product_url    TEXT NOT NULL UNIQUE,
        product_title  TEXT NOT NULL,
        search_keyword TEXT NOT NULL,
        is_active      BOOLEAN NOT NULL DEFAULT true,
        created_at     TIMESTAMPTZ NOT NULL,
        updated_at     TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS scraper_runs (
        id                  UUID PRIMARY KEY,
        loja_id             UUID NOT NULL REFERENCES loja(id),
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
        anuncio_id      UUID REFERENCES anuncio(id),
        product_url     TEXT NOT NULL,
        product_title   TEXT NOT NULL,
        status          TEXT NOT NULL,
        started_at      TIMESTAMPTZ NOT NULL,
        finished_at     TIMESTAMPTZ,
        error_message   TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS coleta_preco (
        id                     UUID PRIMARY KEY,
        anuncio_id             UUID NOT NULL REFERENCES anuncio(id),
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
    """CREATE TABLE IF NOT EXISTS trigger_requests (
        id            UUID PRIMARY KEY,
        loja_id       UUID REFERENCES loja(id),
        status        TEXT NOT NULL,
        requested_at  TIMESTAMPTZ NOT NULL,
        processed_at  TIMESTAMPTZ,
        error_message TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS alert_rules (
        id              UUID PRIMARY KEY,
        loja_id         UUID REFERENCES loja(id),
        produto_id      UUID REFERENCES produto(id),
        search_keyword  TEXT,
        threshold_type  TEXT NOT NULL,
        threshold_value NUMERIC(12,2),
        is_active       BOOLEAN NOT NULL,
        created_at      TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS alert_events (
        id                BIGSERIAL PRIMARY KEY,
        alert_rule_id     UUID NOT NULL REFERENCES alert_rules(id),
        coleta_preco_id   UUID NOT NULL REFERENCES coleta_preco(id),
        reason            TEXT NOT NULL,
        triggered_at      TIMESTAMPTZ NOT NULL
    )""",
]

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_scraper_runs_loja ON scraper_runs(loja_id)",
    "CREATE INDEX IF NOT EXISTS idx_scraper_runs_started_at ON scraper_runs(started_at)",
    "CREATE INDEX IF NOT EXISTS idx_listing_runs_scraper_run ON listing_runs(scraper_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_listing_runs_anuncio ON listing_runs(anuncio_id)",
    "CREATE INDEX IF NOT EXISTS idx_coleta_preco_anuncio ON coleta_preco(anuncio_id, scraped_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_coleta_preco_run ON coleta_preco(scraper_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_trigger_requests_status ON trigger_requests(status)",
    "CREATE INDEX IF NOT EXISTS idx_alert_rules_active ON alert_rules(is_active)",
    "CREATE INDEX IF NOT EXISTS idx_alert_events_rule ON alert_events(alert_rule_id)",
    "CREATE INDEX IF NOT EXISTS idx_anuncio_loja ON anuncio(loja_id)",
    "CREATE INDEX IF NOT EXISTS idx_produto_categoria ON produto(categoria_id)",
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
    jsonb codec so produto.specs round-trips as a plain Python dict instead of
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
