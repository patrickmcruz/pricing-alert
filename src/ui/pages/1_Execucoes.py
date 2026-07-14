import asyncio
import os
import sys

# Ensure src module is in path (this file lives two levels deeper than dashboard.py)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
import streamlit as st

from src.core.config import settings
from src.core.execution import RunStatus, ScraperRunRecord
from src.core.i18n import i18n, t
from src.repositories.sqlite_execution_repository import SQLiteExecutionRepository

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


async def _fetch_latest_runs() -> list[ScraperRunRecord]:
    repo = SQLiteExecutionRepository(DB_PATH)
    # This page only ever reads, but the orchestrator/script that writes runs
    # may not have started yet on a fresh DB - initialize_schema is a no-op
    # CREATE TABLE IF NOT EXISTS, so it's safe to call from here too.
    await repo.initialize_schema()
    return await repo.get_latest_runs()


async def _fetch_run_history(limit: int) -> list[ScraperRunRecord]:
    repo = SQLiteExecutionRepository(DB_PATH)
    await repo.initialize_schema()
    return await repo.get_run_history(limit=limit)


def _load_latest_runs() -> list[ScraperRunRecord]:
    return asyncio.run(_fetch_latest_runs())


def _load_run_history(limit: int = 50) -> list[ScraperRunRecord]:
    return asyncio.run(_fetch_run_history(limit))


@st.fragment(run_every="3s")
def render_live_status() -> None:
    if not os.path.exists(DB_PATH):
        st.info(t("execution_no_data", lang=lang))
        return

    latest_runs = _load_latest_runs()
    if not latest_runs:
        st.info(t("execution_no_data", lang=lang))
        return

    st.subheader(t("execution_live_status", lang=lang))
    cols = st.columns(len(latest_runs))
    for col, run in zip(cols, latest_runs):
        with col:
            st.metric(
                label=run.store_name,
                value=t(STATUS_LABEL_KEYS[run.status], lang=lang),
            )
            st.caption(f"{t('execution_started_at', lang=lang)}: {run.started_at:%Y-%m-%d %H:%M:%S}")
            if run.finished_at:
                st.caption(f"{t('execution_finished_at', lang=lang)}: {run.finished_at:%Y-%m-%d %H:%M:%S}")
            if run.status != RunStatus.RUNNING:
                st.caption(
                    f"{t('execution_skus_succeeded', lang=lang)}: {run.skus_succeeded} · "
                    f"{t('execution_skus_failed', lang=lang)}: {run.skus_failed} · "
                    f"{t('execution_skus_total', lang=lang)}: {run.skus_total}"
                )
            if run.error_message:
                st.error(f"{t('execution_error', lang=lang)}: {run.error_message}")

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
                t("execution_started_at", lang=lang): r.started_at.strftime("%Y-%m-%d %H:%M:%S"),
                t("execution_finished_at", lang=lang): (
                    r.finished_at.strftime("%Y-%m-%d %H:%M:%S") if r.finished_at else "—"
                ),
                t("execution_skus_succeeded", lang=lang): r.skus_succeeded,
                t("execution_skus_failed", lang=lang): r.skus_failed,
                t("execution_error", lang=lang): r.error_message or "",
            }
            for r in history
        ]
    )
    st.dataframe(history_df, hide_index=True, width="stretch")
