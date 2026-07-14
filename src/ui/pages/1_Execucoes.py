import asyncio
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Ensure src module is in path (this file lives two levels deeper than Dashboard.py)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
import streamlit as st

from src.core.config import settings
from src.core.execution import RunStatus, ScraperRunRecord, SkuRunRecord, SkuRunStatus
from src.core.i18n import i18n, t
from src.core.trigger import TriggerRequest
from src.db.schema import initialize_schema as initialize_db_schema
from src.repositories.sqlite_execution_repository import SQLiteExecutionRepository
from src.repositories.sqlite_trigger_repository import SQLiteTriggerRepository

# Force reload of translations so JSON updates are picked up without restarting Streamlit
i18n.load_locales()

DB_PATH = settings.db_path

st.set_page_config(page_title="Scraper Execution Monitor", page_icon="📡", layout="wide")

lang = st.sidebar.selectbox("Idioma / Language", ["pt-BR", "en-US"], index=0, key="execution_lang")

st.title(t("execution_monitor_title", lang=lang))
st.markdown(t("execution_monitor_desc", lang=lang))

STATUS_LABEL_KEYS = {
    RunStatus.RUNNING: "execution_status_running",
    RunStatus.SUCCESS: "execution_status_success",
    RunStatus.FAILED: "execution_status_failed",
}

DISPLAY_TZ = ZoneInfo(settings.display_timezone)


def _fmt_local(dt: datetime) -> str:
    """Converts a UTC (or naive-assumed-UTC) timestamp to settings.display_timezone for display."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(DISPLAY_TZ).strftime("%Y-%m-%d %H:%M:%S")


async def _fetch_latest_runs() -> list[ScraperRunRecord]:
    repo = SQLiteExecutionRepository(DB_PATH)
    # This page only ever reads, but the orchestrator/script that writes runs
    # may not have started yet on a fresh DB - initialize_schema is a no-op
    # CREATE TABLE IF NOT EXISTS, so it's safe to call from here too.
    await initialize_db_schema(DB_PATH)
    return await repo.get_latest_runs()


async def _fetch_run_history(limit: int) -> list[ScraperRunRecord]:
    repo = SQLiteExecutionRepository(DB_PATH)
    await initialize_db_schema(DB_PATH)
    return await repo.get_run_history(limit=limit)


def _load_latest_runs() -> list[ScraperRunRecord]:
    return asyncio.run(_fetch_latest_runs())


def _load_run_history(limit: int = 50) -> list[ScraperRunRecord]:
    return asyncio.run(_fetch_run_history(limit))


async def _fetch_sku_progress(run_id) -> tuple[SkuRunRecord | None, dict[SkuRunStatus, int]]:
    repo = SQLiteExecutionRepository(DB_PATH)
    await initialize_db_schema(DB_PATH)
    current = await repo.get_current_sku_run(run_id)
    counts = await repo.get_sku_run_counts(run_id)
    return current, counts


def _load_sku_progress(run_id) -> tuple[SkuRunRecord | None, dict[SkuRunStatus, int]]:
    return asyncio.run(_fetch_sku_progress(run_id))


async def _fetch_active_triggers() -> list[TriggerRequest]:
    repo = SQLiteTriggerRepository(DB_PATH)
    await initialize_db_schema(DB_PATH)
    return await repo.get_active_requests()


def _load_active_triggers() -> list[TriggerRequest]:
    return asyncio.run(_fetch_active_triggers())


async def _submit_trigger(store_name: str | None) -> None:
    repo = SQLiteTriggerRepository(DB_PATH)
    await initialize_db_schema(DB_PATH)
    await repo.create_request(store_name)


def _request_run(store_name: str | None = None) -> None:
    asyncio.run(_submit_trigger(store_name))
    st.toast(t("execution_trigger_queued", lang=lang), icon="🚀")


@st.fragment(run_every="3s")
def render_live_status() -> None:
    if not os.path.exists(DB_PATH):
        st.info(t("execution_no_data", lang=lang))
        return

    active_triggers = _load_active_triggers()
    run_all_pending = any(tr.store_name is None for tr in active_triggers)

    action_col, note_col = st.columns([1, 3])
    with action_col:
        if st.button(
            f"▶️ {t('execution_run_all_now', lang=lang)}",
            disabled=run_all_pending,
            width="stretch",
            key="run_all_now_btn",
        ):
            _request_run(None)
    with note_col:
        if active_triggers:
            st.caption(f"⏳ {t('execution_trigger_pending_note', lang=lang, count=len(active_triggers))}")

    latest_runs = _load_latest_runs()
    if not latest_runs:
        st.info(t("execution_no_data", lang=lang))
        return

    pending_stores = {tr.store_name for tr in active_triggers if tr.store_name}

    st.subheader(t("execution_live_status", lang=lang))
    cols = st.columns(len(latest_runs))
    for col, run in zip(cols, latest_runs):
        with col:
            st.metric(
                label=run.store_name,
                value=t(STATUS_LABEL_KEYS[run.status], lang=lang),
            )
            st.caption(f"{t('execution_started_at', lang=lang)}: {_fmt_local(run.started_at)}")
            if run.finished_at:
                st.caption(f"{t('execution_finished_at', lang=lang)}: {_fmt_local(run.finished_at)}")
            if run.status != RunStatus.RUNNING:
                st.caption(
                    f"{t('execution_skus_succeeded', lang=lang)}: {run.listings_succeeded} · "
                    f"{t('execution_skus_failed', lang=lang)}: {run.listings_failed} · "
                    f"{t('execution_skus_total', lang=lang)}: {run.listings_total}"
                )
            else:
                # scraper_runs' own counters only get written once, at the very
                # end (finish_run) - while RUNNING they're still zero, so the
                # live picture comes from sku_runs instead: which SKU is being
                # scraped right now, and how many have been processed so far.
                current_sku, sku_counts = _load_sku_progress(run.run_id)
                succeeded_live = sku_counts.get(SkuRunStatus.SUCCESS, 0)
                running_live = sku_counts.get(SkuRunStatus.RUNNING, 0)
                done_live = sum(sku_counts.values()) - running_live
                failed_live = done_live - succeeded_live
                if done_live:
                    st.caption(
                        t(
                            "execution_sku_progress",
                            lang=lang,
                            done=done_live,
                            ok=succeeded_live,
                            fail=failed_live,
                        )
                    )
                if current_sku:
                    title = current_sku.product_title
                    if len(title) > 40:
                        title = title[:40] + "…"
                    st.caption(f"🔄 {t('execution_sku_in_progress', lang=lang)}: {title}")
            if run.error_message:
                st.error(f"{t('execution_error', lang=lang)}: {run.error_message}")

            if st.button(
                f"▶️ {t('execution_run_store_now', lang=lang)}",
                key=f"run_now_{run.store_name}",
                disabled=run.status == RunStatus.RUNNING or run.store_name in pending_stores,
                width="stretch",
            ):
                _request_run(run.store_name)

    st.caption(f"🔄 {t('execution_auto_refresh_note', lang=lang)}")


render_live_status()

st.divider()
st.subheader(t("execution_history_title", lang=lang))

history = _load_run_history(limit=50)
if not history:
    st.info(t("execution_no_data", lang=lang))
else:
    history_df = pd.DataFrame(
        [
            {
                t("col_store", lang=lang): r.store_name,
                t("execution_status_col", lang=lang): t(STATUS_LABEL_KEYS[r.status], lang=lang),
                t("execution_started_at", lang=lang): _fmt_local(r.started_at),
                t("execution_finished_at", lang=lang): (
                    _fmt_local(r.finished_at) if r.finished_at else "—"
                ),
                t("execution_skus_succeeded", lang=lang): r.listings_succeeded,
                t("execution_skus_failed", lang=lang): r.listings_failed,
                t("execution_error", lang=lang): r.error_message or "",
            }
            for r in history
        ]
    )
    st.dataframe(history_df, hide_index=True, width="stretch")
