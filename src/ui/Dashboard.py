import os
import sys

# Ensure src module is in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px
from src.core.config import settings
from src.core.i18n import t, i18n

# Force reload of translations so JSON updates are picked up without restarting Streamlit
i18n.load_locales()

DB_PATH = settings.db_path

st.set_page_config(page_title="GPU Price Tracker", layout="wide")

lang = st.sidebar.selectbox("Idioma / Language", ["pt-BR", "en-US"], index=0)

st.title(t("app_title", lang=lang))
st.markdown(t("app_desc", lang=lang))


def load_data():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM prices", conn)
        conn.close()

        if not df.empty:
            # Schema validation: Ensure critical columns exist. If not, inject empty columns gracefully.
            required_cols = ["brand", "model", "discount", "price_installments", "installment_count", "parser_version"]
            for col in required_cols:
                if col not in df.columns:
                    df[col] = pd.NA
                    
            df["scraped_at"] = pd.to_datetime(df["scraped_at"])
            # Convert from UTC to America/Sao_Paulo (GMT-3)
            if df["scraped_at"].dt.tz is None:
                df["scraped_at"] = df["scraped_at"].dt.tz_localize("UTC")
            df["scraped_at"] = df["scraped_at"].dt.tz_convert("America/Sao_Paulo")
            # Remove tzinfo so Streamlit formats it cleanly
            df["scraped_at"] = df["scraped_at"].dt.tz_localize(None)
            
            # --- VALIDADOR DE DADOS ---
            # Removemos qualquer registro com preço zero ou negativo, pois distorcem 
            # os gráficos e os cálculos de "menor preço histórico"
            df = df[df["price_cash"] > 0]
            if "price_installments" in df.columns:
                df = df[(df["price_installments"] > 0) | df["price_installments"].isna()]
            
            # Create a composite product name for clear differentiation
            df["product_name"] = df.apply(
                lambda row: f"{row['brand']} {row['model']}" if pd.notna(row.get('brand')) and pd.notna(row.get('model')) else row['search_keyword'].upper(),
                axis=1
            )
            
            df = df.sort_values(by="scraped_at", ascending=False)
        return df
    except Exception as e:
        st.error(f"Failed to load data: {e}")
        return pd.DataFrame()


df = load_data()

if df.empty:
    st.info(t("no_data_db", lang=lang))
else:
    # Global column definitions
    df["manufacturer"] = df["search_keyword"].apply(
        lambda k: "NVIDIA" if any(x in str(k).lower() for x in ["rtx", "gtx"]) else ("AMD" if any(x in str(k).lower() for x in ["rx ", "rx-", "radeon"]) else "Outros")
    )

    # Sidebar Filters (Global)
    st.sidebar.header(t("sidebar_filters", lang=lang))

    # 1. Selecionar Lojas
    stores = df["store_name"].unique().tolist()
    default_stores = [s for s in settings.default_stores if s in stores] if settings.default_stores else stores
    selected_stores = st.sidebar.multiselect(t("select_stores", lang=lang), stores, default=default_stores, placeholder=t("choose_option", lang=lang))

    # 2. Selecionar Fabricante
    manufacturers = df["manufacturer"].dropna().unique().tolist()
    default_mf = [settings.default_manufacturer] if settings.default_manufacturer in manufacturers else manufacturers
    selected_mfs = st.sidebar.multiselect(t("select_manufacturer", lang=lang), manufacturers, default=default_mf, placeholder=t("choose_option", lang=lang))

    # 3. Selecionar GPUs
    # Compute intermediate filtered df for GPU options based on selected manufacturer
    mf_df = df[df["manufacturer"].isin(selected_mfs)] if selected_mfs else df
    keyword_min_prices = mf_df.groupby("search_keyword")["price_cash"].min().sort_values()
    keywords = keyword_min_prices.index.tolist()

    default_keywords = [k for k in keywords if k in settings.default_gpus]
    if len(default_keywords) < 2:
        for k in keywords:
            if k not in default_keywords:
                default_keywords.append(k)
            if len(default_keywords) == 2:
                break

    selected_keywords = st.sidebar.multiselect(
        t("select_gpus", lang=lang), keywords, default=default_keywords, max_selections=2, placeholder=t("choose_option", lang=lang), key="global_keywords"
    )
    selected_keywords = sorted(selected_keywords, key=lambda k: keywords.index(k))

    # 4. Selecionar Marcas
    brands = df["brand"].dropna().unique().tolist()
    default_brands = [b for b in settings.default_brands if b in brands] if settings.default_brands else brands
    selected_brands = st.sidebar.multiselect(t("select_brands", lang=lang), brands, default=default_brands, placeholder=t("choose_option", lang=lang))

    # Apply Global Filters
    global_df = df[
        (df["store_name"].isin(selected_stores)) &
        (df["manufacturer"].isin(selected_mfs)) &
        (df["search_keyword"].isin(selected_keywords))
    ]
    if selected_brands:
        global_df = global_df[global_df["brand"].isin(selected_brands) | global_df["brand"].isna()]

    # Main UI Navigation (Using segmented_control to preserve state across reruns)
    tab_options = [t("tab_compare", lang=lang), t("tab_overview", lang=lang)]
    
    if hasattr(st, "segmented_control"):
        # If language changed, the old translated tab string won't be in the new options list.
        if "active_tab" not in st.session_state or st.session_state.active_tab not in tab_options:
            st.session_state.active_tab = tab_options[0]
            
        active_tab = st.segmented_control(
            "Navegação",
            options=tab_options,
            label_visibility="collapsed",
            key="active_tab"
        )
        if not active_tab: # if user unselects
            active_tab = tab_options[0]
    else:
        active_tab = st.radio(
            "Navegação",
            options=tab_options,
            horizontal=True,
            label_visibility="collapsed",
        )

    if active_tab == tab_options[0]:
        if global_df.empty:
            st.warning(t("no_data_filters", lang=lang))
        else:
            # global_df is already filtered by selected_keywords from the sidebar
            filtered_df = global_df.copy()
            
            if filtered_df.empty:
                st.warning(t("no_data_filters", lang=lang))
            else:
                # KPIs
                st.subheader(t("market_overview", lang=lang))
                cols = st.columns(max(len(selected_keywords), 1))
        
                for idx, keyword in enumerate(selected_keywords):
                    with cols[idx]:
                        keyword_df = filtered_df[filtered_df["search_keyword"] == keyword]
                        if not keyword_df.empty:
                            # 1. Calculate Current Market (Latest scrape for each product_url)
                            idx_latest = keyword_df.groupby("product_url")["scraped_at"].idxmax()
                            current_market = keyword_df.loc[idx_latest]
                            
                            if current_market.empty:
                                continue
                                
                            # 2. Extract Metrics
                            best_current_idx = current_market["price_cash"].idxmin()
                            best_current = current_market.loc[best_current_idx]
                            
                            best_historical_idx = keyword_df["price_cash"].idxmin()
                            best_historical = keyword_df.loc[best_historical_idx]
                            
                            avg_current = current_market["price_cash"].mean()
                            
                            st.markdown(f"**{t('market_title', lang=lang, keyword=keyword.upper())}**")
                            
                            kpi_col1, kpi_col2 = st.columns(2)
                            
                            # Diff vs Historical
                            diff_from_hist = best_current['price_cash'] - best_historical['price_cash']
                            if diff_from_hist == 0:
                                delta_str = t("matches_low", lang=lang)
                                delta_col = "normal"
                            else:
                                delta_str = t("vs_low", lang=lang, diff=f"{diff_from_hist:,.2f}")
                                delta_col = "inverse" # Red means higher than historical low
                                
                            kpi_col1.metric(
                                label=t("best_deal", lang=lang),
                                value=f"R$ {best_current['price_cash']:,.2f}",
                                delta=delta_str,
                                delta_color=delta_col,
                            )
                            kpi_col1.markdown(f"*{best_current['store_name']} - {best_current['model']}* [**↗️**]({best_current['product_url']})")
                            
                            kpi_col2.metric(
                                label=t("all_time_low", lang=lang),
                                value=f"R$ {best_historical['price_cash']:,.2f}"
                            )
                            
                            kpi_col3, kpi_col4 = st.columns(2)
                            
                            if "price_installments" in current_market.columns and not current_market["price_installments"].isna().all():
                                best_inst_idx = current_market["price_installments"].idxmin()
                                best_inst = current_market.loc[best_inst_idx]
                                
                                hist_best_inst_idx = keyword_df["price_installments"].idxmin()
                                hist_best_inst = keyword_df.loc[hist_best_inst_idx]
                                
                                inst_diff_from_hist = best_inst['price_installments'] - hist_best_inst['price_installments']
                                if inst_diff_from_hist == 0:
                                    inst_delta_str = t("matches_low", lang=lang)
                                    inst_delta_col = "normal"
                                else:
                                    inst_delta_str = t("vs_low", lang=lang, diff=f"{inst_diff_from_hist:,.2f}")
                                    inst_delta_col = "inverse"
                                    
                                kpi_col3.metric(
                                    label=t("best_inst", lang=lang),
                                    value=f"R$ {best_inst['price_installments']:,.2f}",
                                    delta=inst_delta_str,
                                    delta_color=inst_delta_col,
                                )
                                kpi_col3.markdown(f"*{best_inst['store_name']} - {best_inst['model']}* [**{t('go_to_store', lang=lang)}**]({best_inst['product_url']})")
                                
                                kpi_col4.metric(
                                    label=t("all_time_low_inst", lang=lang),
                                    value=f"R$ {hist_best_inst['price_installments']:,.2f}"
                                )
                            else:
                                kpi_col3.metric(t("best_inst", lang=lang), t("na", lang=lang))
                                kpi_col4.metric(t("all_time_low_inst", lang=lang), t("na", lang=lang))
                
                # Price Trends
                st.markdown("<br>", unsafe_allow_html=True)
                st.divider()
                st.subheader(t("price_trends", lang=lang))
                
                if selected_keywords:
                    # Unify the trend chart to compare the lowest prices of the selected models
                    filtered_df["scrape_minute"] = filtered_df["scraped_at"].dt.floor("Min")
                    idx_min = filtered_df.groupby(["scrape_minute", "search_keyword"])["price_cash"].idxmin()
                    trend_data = filtered_df.loc[idx_min].sort_values("scrape_minute")
                    
                    if not trend_data.empty:
                        fig = px.line(
                            trend_data,
                            x="scrape_minute",
                            y="price_cash",
                            color="search_keyword",
                            title=t("price_history_compare", lang=lang),
                            markers=True,
                            hover_data=["product_name", "store_name"]
                        )
                        fig.update_xaxes(
                            title_text="",
                            tickformatstops=[
                                dict(dtickrange=[None, 3600000], value="%H:%M"), 
                                dict(dtickrange=[3600000, 86400000], value="%d %b\n%H:00"), 
                                dict(dtickrange=[86400000, None], value="%d %b %Y") 
                            ]
                        )
                        fig.update_traces(
                            hovertemplate="<b>%{customdata[0]}</b><br>Store: %{customdata[1]}<br>Price: R$ %{y:,.2f}<br>Date: %{x}<extra></extra>"
                        )
                        fig.update_layout(
                            margin=dict(l=10, r=10, t=30, b=10),
                            legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5, title="")
                        )
                        st.plotly_chart(fig, width='stretch')
                    else:
                        st.info(t("no_trend_data", lang=lang, keyword=""))

                # ----- Detailed Product View -----
                st.markdown("<br>", unsafe_allow_html=True)
                st.divider()
                st.subheader(t("detailed_view", lang=lang))
                
                if selected_keywords:
                    main_cols = st.columns(len(selected_keywords))
                    for idx, keyword in enumerate(selected_keywords):
                        with main_cols[idx]:
                            keyword_df = filtered_df[filtered_df["search_keyword"] == keyword]
                            if keyword_df.empty:
                                st.warning(f"No data for {keyword.upper()}")
                                continue
                                
                            st.markdown(f"### {keyword.upper()}")
                            
                            # Let user pick a single product from the filtered set, sorted by lowest price
                            product_min_prices = keyword_df.groupby("product_name")["price_cash"].min().sort_values()
                            product_options = product_min_prices.index.tolist()
                            selected_product = st.selectbox(t("select_model", lang=lang), product_options, index=0, key=f"select_{keyword}")
                            product_df = keyword_df[keyword_df["product_name"] == selected_product].sort_values(by="scraped_at")
                            
                            if not product_df.empty:
                                # 1. Calculate Current Market for this specific product
                                idx_latest_prod = product_df.groupby("product_url")["scraped_at"].idxmax()
                                current_prod_market = product_df.loc[idx_latest_prod]
                                
                                if current_prod_market.empty:
                                    continue
                                    
                                # 2. Extract Metrics
                                best_current_idx = current_prod_market["price_cash"].idxmin()
                                best_current = current_prod_market.loc[best_current_idx]
                                
                                lowest_price = product_df["price_cash"].min()
                                avg_price = current_prod_market["price_cash"].mean()
                                
                                st.markdown(t("analytics", lang=lang))
                                col1, col2 = st.columns(2)
                                
                                # Diff vs Historical
                                diff_from_hist = best_current['price_cash'] - lowest_price
                                if diff_from_hist == 0:
                                    delta_str = t("matches_low", lang=lang)
                                    delta_col = "normal"
                                else:
                                    delta_str = t("vs_low", lang=lang, diff=f"{diff_from_hist:,.2f}")
                                    delta_col = "inverse"
                                    
                                col1.metric(
                                    label=t("current_best_price", lang=lang),
                                    value=f"R$ {best_current['price_cash']:,.2f}",
                                    delta=delta_str,
                                    delta_color=delta_col,
                                )
                                col1.markdown(f"*{best_current['store_name']}* [**{t('go_to_store', lang=lang)}**]({best_current['product_url']})")
                                
                                col2.metric(
                                    label=t("all_time_low", lang=lang),
                                    value=f"R$ {lowest_price:,.2f}"
                                )
                                
                                col3, col4 = st.columns(2)
                                
                                if "price_installments" in current_prod_market.columns and not current_prod_market["price_installments"].isna().all():
                                    best_inst_idx = current_prod_market["price_installments"].idxmin()
                                    best_inst = current_prod_market.loc[best_inst_idx]
                                    
                                    lowest_inst_price = product_df["price_installments"].min()
                                    inst_diff_from_hist = best_inst['price_installments'] - lowest_inst_price
                                    if inst_diff_from_hist == 0:
                                        inst_delta_str = t("matches_low", lang=lang)
                                        inst_delta_col = "normal"
                                    else:
                                        inst_delta_str = t("vs_low", lang=lang, diff=f"{inst_diff_from_hist:,.2f}")
                                        inst_delta_col = "inverse"
                                        
                                    col3.metric(
                                        label=t("best_inst", lang=lang),
                                        value=f"R$ {best_inst['price_installments']:,.2f}",
                                        delta=inst_delta_str,
                                        delta_color=inst_delta_col,
                                    )
                                    col3.markdown(f"*{best_inst['store_name']}* [**{t('go_to_store', lang=lang)}**]({best_inst['product_url']})")
                                    
                                    col4.metric(
                                        label=t("all_time_low_inst", lang=lang),
                                        value=f"R$ {lowest_inst_price:,.2f}"
                                    )
                                else:
                                    col3.metric(t("best_inst", lang=lang), t("na", lang=lang))
                                    col4.metric(t("all_time_low_inst", lang=lang), t("na", lang=lang))
                    
                                # Detailed line chart for the selected product
                                lbl_cash = t("label_cash", lang=lang)
                                lbl_inst = t("label_inst", lang=lang)
                                lbl_spread = t("label_spread", lang=lang)
                                
                                plot_df = product_df.copy()
                                plot_df[lbl_cash] = plot_df["price_cash"]
                                plot_df[lbl_inst] = plot_df["price_installments"]
                                plot_df[lbl_spread] = plot_df["price_installments"] - plot_df["price_cash"]
                                
                                detail_fig = px.line(
                                    plot_df,
                                    x="scraped_at",
                                    y=[lbl_cash, lbl_inst],
                                    title=t("price_history_title", lang=lang, keyword=""),
                                    markers=True,
                                    color_discrete_sequence=["#1f77b4", "#ff7f0e"]
                                )
                                detail_fig.update_traces(
                                    hovertemplate="<b>%{data.name}</b>: R$ %{y:,.2f}<extra></extra>"
                                )
                                # Adjust layout for narrow columns
                                detail_fig.update_layout(
                                    margin=dict(l=10, r=10, t=30, b=10),
                                    yaxis_title=t("yaxis_price", lang=lang),
                                    legend_title="",
                                    legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
                                    hovermode="x unified" # Shows all labels when hovering vertically
                                )
                                detail_fig.update_xaxes(
                                    title_text="",
                                    tickformatstops=[
                                        dict(dtickrange=[None, 3600000], value="%H:%M"),
                                        dict(dtickrange=[3600000, 86400000], value="%d %b"),
                                        dict(dtickrange=[86400000, None], value="%d %b")
                                    ]
                                )
                                st.plotly_chart(detail_fig, width='stretch')

                                # Spread / Tax Chart
                                spread_fig = px.bar(
                                    plot_df,
                                    x="scraped_at",
                                    y=lbl_spread,
                                    title=f"💸 {lbl_spread}",
                                    color=lbl_spread,
                                    color_continuous_scale="RdYlGn_r", # High cost is red, low cost is green
                                    text=lbl_spread
                                )
                                spread_fig.update_layout(
                                    margin=dict(l=10, r=10, t=30, b=10),
                                    yaxis_title=t("yaxis_tax", lang=lang),
                                    xaxis_title="",
                                    coloraxis_showscale=False, # Hide the color bar legend
                                    hovermode="x unified"
                                )
                                hover_tax_lbl = t("hover_tax", lang=lang)
                                spread_fig.update_traces(
                                    texttemplate='R$ %{text:,.2f}',
                                    textposition='outside',
                                    hovertemplate=f"<b>{hover_tax_lbl}</b>: R$ %{{y:,.2f}}<extra></extra>"
                                )
                                st.plotly_chart(spread_fig, width='stretch')

    elif active_tab == tab_options[1]:
        st.subheader(t("raw_data", lang=lang))
        
        overview_df = global_df.copy()
        
        if overview_df.empty:
            st.warning(t("no_data_filters", lang=lang))
        else:
            display_df = overview_df.copy()
            display_df = display_df[
                [
                    "scraped_at",
                    "store_name",
                    "search_keyword",
                    "brand",
                    "model",
                    "price_cash",
                    "price_installments",
                    "installment_count",
                    "discount",
                    "parser_version",
                    "is_available",
                    "product_url",
                ]
            ]
    
            # Translate column names
            column_translations = {
                "scraped_at": t("col_scraped_at", lang=lang),
                "store_name": t("col_store", lang=lang),
                "search_keyword": t("col_keyword", lang=lang),
                "brand": t("col_brand", lang=lang),
                "model": t("col_model", lang=lang),
                "price_cash": t("col_price_cash", lang=lang),
                "price_installments": t("col_price_inst", lang=lang),
                "installment_count": t("col_inst_count", lang=lang),
                "discount": t("col_discount", lang=lang),
                "parser_version": t("col_parser_ver", lang=lang),
                "is_available": t("col_available", lang=lang),
                "product_url": t("col_url", lang=lang),
            }
            display_df = display_df.rename(columns=column_translations)
    
            st.markdown(t("filter_raw_data", lang=lang))
            f_col1, f_col2, f_col3 = st.columns([2, 2, 1])
            filter_col = f_col1.selectbox(t("select_col", lang=lang), options=["None"] + list(display_df.columns), key="overview_filter_col")
            if filter_col != "None":
                unique_values = display_df[filter_col].dropna().unique().tolist()
                selected_values = f_col2.multiselect(t("select_val", lang=lang, col=filter_col), options=unique_values, default=unique_values, key="overview_selected_vals")
                display_df = display_df[display_df[filter_col].isin(selected_values) | display_df[filter_col].isna()]
            
            items_per_page = f_col3.selectbox(
                "Itens/página" if lang == "pt-BR" else "Items/page", 
                options=[10, 50, 100, 200, 500], 
                index=2, 
                key="items_per_page"
            )

            # Pagination logic
            total_items = len(display_df)
            total_pages = max(1, (total_items + items_per_page - 1) // items_per_page)
            
            if "raw_data_page" not in st.session_state:
                st.session_state.raw_data_page = 1
                
            # Reset page if out of bounds (e.g. after filtering)
            if st.session_state.raw_data_page > total_pages:
                st.session_state.raw_data_page = 1
                
            start_idx = (st.session_state.raw_data_page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            paginated_df = display_df.iloc[start_idx:end_idx]
            
            # Calculate height to fit rows (approx 35px per row + 40px header)
            table_height = (len(paginated_df) * 35) + 40
            
            # Configure columns for better display
            st.dataframe(
                paginated_df,
                height=table_height,
                column_config={
                    t("col_url", lang=lang): st.column_config.LinkColumn(
                        t("col_url", lang=lang),
                        display_text=r"(.*)"
                    ),
                    t("col_scraped_at", lang=lang): st.column_config.DatetimeColumn(
                        t("col_scraped_at", lang=lang), format="YYYY-MM-DD HH:mm:ss"
                    ),
                    t("col_price_cash", lang=lang): st.column_config.NumberColumn(
                        t("col_price_cash", lang=lang), format="R$ %.2f"
                    ),
                    t("col_price_inst", lang=lang): st.column_config.NumberColumn(
                        t("col_price_inst", lang=lang), format="R$ %.2f"
                    ),
                },
                hide_index=True,
                width='stretch',
            )
            
            # Pagination Controls
            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.button(t("btn_prev", lang=lang), disabled=(st.session_state.raw_data_page == 1)):
                    st.session_state.raw_data_page -= 1
                    st.rerun()
            with col2:
                page_info_str = t("page_info", lang=lang, page=st.session_state.raw_data_page, total=total_pages, items=total_items)
                st.markdown(f"<div style='text-align: center; padding-top: 8px;'><b>{page_info_str}</b></div>", unsafe_allow_html=True)
            with col3:
                # Use a container to right-align the next button
                with st.container():
                    st.markdown('<style>div.stButton > button:first-child {float: right;}</style>', unsafe_allow_html=True)
                    if st.button(t("btn_next", lang=lang), disabled=(st.session_state.raw_data_page == total_pages)):
                        st.session_state.raw_data_page += 1
                        st.rerun()
