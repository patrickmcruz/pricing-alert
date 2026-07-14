import asyncio
import os
import sys

# Ensure src module is in path (this file lives two levels deeper than dashboard.py)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st
from pydantic import ValidationError

from src.core.catalog import Brand, GpuChipset, GpuModel, infer_chip_maker
from src.core.config import settings
from src.core.contract import ProductSKU
from src.core.i18n import i18n, t
from src.core.registry import get_registered_scrapers
from src.repositories.sqlite_catalog_repository import SQLiteCatalogRepository
from src.repositories.sqlite_repository import SQLitePriceRepository
import src.scrapers  # noqa: F401 - importing the package triggers scraper self-registration

# Force reload of translations so JSON updates are picked up without restarting Streamlit
i18n.load_locales()

DB_PATH = settings.db_path

st.set_page_config(page_title="Gerenciar GPUs", page_icon="🎮", layout="wide")

lang = st.sidebar.selectbox("Idioma / Language", ["pt-BR", "en-US"], index=0, key="gpu_lang")

st.title(t("gpu_manage_title", lang=lang))
st.markdown(t("gpu_manage_desc", lang=lang))


async def _fetch_page_data() -> tuple[list[ProductSKU], list[Brand], list[GpuChipset]]:
    price_repo = SQLitePriceRepository(DB_PATH)
    await price_repo.initialize_schema()
    catalog_repo = SQLiteCatalogRepository(DB_PATH)
    await catalog_repo.initialize_schema()
    all_skus = await price_repo.list_all_skus()
    brands = await catalog_repo.list_brands()
    chipsets = await catalog_repo.list_chipsets()
    return all_skus, brands, chipsets


def _load_page_data() -> tuple[list[ProductSKU], list[Brand], list[GpuChipset]]:
    return asyncio.run(_fetch_page_data())


async def _fetch_gpu_model(gpu_model_id: str) -> GpuModel | None:
    catalog_repo = SQLiteCatalogRepository(DB_PATH)
    await catalog_repo.initialize_schema()
    return await catalog_repo.get_gpu_model(gpu_model_id)


def _load_gpu_model(gpu_model_id: str) -> GpuModel | None:
    return asyncio.run(_fetch_gpu_model(gpu_model_id))


async def _resolve_and_save_sku(
    store_name: str,
    chipset_name: str,
    brand_name: str,
    variant_name: str,
    product_url: str,
    product_title: str,
) -> None:
    catalog_repo = SQLiteCatalogRepository(DB_PATH)
    await catalog_repo.initialize_schema()
    chipset = await catalog_repo.get_or_create_chipset(
        chipset_name, chip_maker=infer_chip_maker(chipset_name)
    )
    brand = await catalog_repo.get_or_create_brand(brand_name)
    gpu_model = await catalog_repo.get_or_create_gpu_model(brand.id, chipset.id, variant_name)

    sku = ProductSKU(
        store_name=store_name,
        search_keyword=chipset.name,
        product_url=product_url,
        gpu_model_id=gpu_model.id,
        brand=brand.name,
        model=gpu_model.variant_name,
        product_title=product_title,
    )

    price_repo = SQLitePriceRepository(DB_PATH)
    await price_repo.initialize_schema()
    await price_repo.save_skus([sku])


async def _remove_sku(product_url: str) -> None:
    repo = SQLitePriceRepository(DB_PATH)
    await repo.initialize_schema()
    await repo.delete_sku(product_url)


all_skus, brands, chipsets = _load_page_data()

editing_sku: ProductSKU | None = st.session_state.get("gpu_editing_sku")
editing_gpu_model: GpuModel | None = _load_gpu_model(editing_sku.gpu_model_id) if editing_sku else None
# Keying widgets by the identity of the SKU being edited (or "new") forces
# Streamlit to reset their values whenever the user switches between add mode
# and editing a different row, instead of reusing stale session_state values.
edit_suffix = str(editing_sku.product_url) if editing_sku else "new"

st.subheader(t("gpu_edit_title", lang=lang) if editing_sku else t("gpu_add_title", lang=lang))

OTHER_SENTINEL = t("gpu_field_keyword_other_option", lang=lang)

# -- Chipset (keyword) picker: existing chipsets from the catalog, + "Outro/Other" to create one.
chipset_names = sorted({c.name for c in chipsets} | ({editing_sku.search_keyword} if editing_sku else set()))
chipset_options = chipset_names + [OTHER_SENTINEL]
default_chipset_index = (
    chipset_options.index(editing_sku.search_keyword)
    if editing_sku and editing_sku.search_keyword in chipset_options
    else 0
)
chipset_choice = st.selectbox(
    t("gpu_field_keyword", lang=lang),
    chipset_options,
    index=default_chipset_index,
    key=f"gpu_chipset_choice_{edit_suffix}",
)
custom_chipset_name = ""
if chipset_choice == OTHER_SENTINEL:
    custom_chipset_name = st.text_input(
        t("gpu_field_keyword_other", lang=lang), key=f"gpu_chipset_custom_{edit_suffix}"
    )

# -- Brand picker: existing brands from the catalog, + "Outro/Other" to create one.
brand_names = sorted({b.name for b in brands} | ({editing_sku.brand} if editing_sku and editing_sku.brand else set()))
brand_options = brand_names + [OTHER_SENTINEL]
default_brand_index = (
    brand_options.index(editing_sku.brand)
    if editing_sku and editing_sku.brand in brand_options
    else 0
)
brand_choice = st.selectbox(
    t("gpu_field_brand", lang=lang),
    brand_options,
    index=default_brand_index,
    key=f"gpu_brand_choice_{edit_suffix}",
)
custom_brand_name = ""
if brand_choice == OTHER_SENTINEL:
    custom_brand_name = st.text_input(
        t("gpu_field_brand_other", lang=lang), key=f"gpu_brand_custom_{edit_suffix}"
    )

if editing_sku and st.button(t("gpu_cancel_edit", lang=lang), key="gpu_cancel_edit_btn"):
    st.session_state["gpu_editing_sku"] = None
    st.rerun()

with st.form(key=f"gpu_form_{edit_suffix}", clear_on_submit=not bool(editing_sku)):
    store_options = sorted(
        set(get_registered_scrapers().keys()) | ({editing_sku.store_name} if editing_sku else set())
    )
    default_store_index = store_options.index(editing_sku.store_name) if editing_sku else 0
    store_name = st.selectbox(
        t("gpu_field_store", lang=lang), store_options, index=default_store_index, key=f"gpu_store_{edit_suffix}"
    )
    product_url = st.text_input(
        t("gpu_field_url", lang=lang),
        value=str(editing_sku.product_url) if editing_sku else "",
        disabled=bool(editing_sku),
        key=f"gpu_url_{edit_suffix}",
    )
    if editing_sku:
        st.caption(t("gpu_url_readonly_note", lang=lang))
    variant_name = st.text_input(
        t("gpu_field_model", lang=lang),
        value=(editing_gpu_model.variant_name if editing_gpu_model else "") if editing_sku else "",
        key=f"gpu_variant_{edit_suffix}",
    )
    product_title = st.text_input(
        t("gpu_field_title", lang=lang),
        value=editing_sku.product_title if editing_sku else "",
        key=f"gpu_title_{edit_suffix}",
    )
    submit_label = t("gpu_submit_save", lang=lang) if editing_sku else t("gpu_submit_add", lang=lang)
    submitted = st.form_submit_button(submit_label, width="stretch")

    if submitted:
        final_chipset_name = custom_chipset_name.strip().lower() if chipset_choice == OTHER_SENTINEL else chipset_choice
        final_brand_name = custom_brand_name.strip() if brand_choice == OTHER_SENTINEL else brand_choice
        final_url = str(editing_sku.product_url) if editing_sku else product_url.strip()

        if not final_chipset_name:
            st.error(t("gpu_field_keyword_other", lang=lang))
        elif not final_brand_name:
            st.error(t("gpu_field_brand_other", lang=lang))
        elif not variant_name.strip():
            st.error(t("gpu_field_model", lang=lang))
        elif not product_title.strip():
            st.error(t("gpu_field_title", lang=lang))
        else:
            try:
                asyncio.run(
                    _resolve_and_save_sku(
                        store_name=store_name,
                        chipset_name=final_chipset_name,
                        brand_name=final_brand_name,
                        variant_name=variant_name.strip(),
                        product_url=final_url,
                        product_title=product_title.strip(),
                    )
                )
            except ValidationError as e:
                st.error(t("gpu_invalid_url", lang=lang, error=str(e)))
            else:
                st.toast(
                    t("gpu_updated_toast" if editing_sku else "gpu_added_toast", lang=lang), icon="✅"
                )
                st.session_state["gpu_editing_sku"] = None
                st.rerun()

st.divider()
st.subheader(t("gpu_list_title", lang=lang))

ALL_STORES_LABEL = t("gpu_filter_all_stores", lang=lang)
store_filter_options = [ALL_STORES_LABEL] + sorted({sku.store_name for sku in all_skus})
store_filter = st.selectbox(t("gpu_filter_store", lang=lang), store_filter_options, key="gpu_store_filter")

filtered_skus = [
    sku for sku in all_skus if store_filter == ALL_STORES_LABEL or sku.store_name == store_filter
]

if not filtered_skus:
    st.info(t("gpu_no_data", lang=lang))
else:
    for sku in filtered_skus:
        with st.container(border=True):
            title_col, brand_col, model_col, link_col, edit_col, delete_col = st.columns(
                [3, 2, 2, 1, 1, 1]
            )
            title_col.markdown(f"**{sku.product_title}**  \n{sku.store_name} · {sku.search_keyword}")
            brand_col.caption(sku.brand or "—")
            model_col.caption(sku.model or "—")
            link_col.markdown(f"[🔗]({sku.product_url})")

            if edit_col.button(t("gpu_edit_btn", lang=lang), key=f"gpu_edit_{sku.product_url}", width="stretch"):
                st.session_state["gpu_editing_sku"] = sku
                st.rerun()

            if delete_col.button(
                t("gpu_delete_btn", lang=lang), key=f"gpu_delete_{sku.product_url}", width="stretch"
            ):
                asyncio.run(_remove_sku(str(sku.product_url)))
                st.toast(t("gpu_deleted_toast", lang=lang), icon="🗑️")
                st.rerun()
