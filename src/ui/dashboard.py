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
            df["scraped_at"] = pd.to_datetime(df["scraped_at"])
            # Convert from UTC to America/Sao_Paulo (GMT-3)
            if df["scraped_at"].dt.tz is None:
                df["scraped_at"] = df["scraped_at"].dt.tz_localize("UTC")
            df["scraped_at"] = df["scraped_at"].dt.tz_convert("America/Sao_Paulo")
            # Remove tzinfo so Streamlit formats it cleanly
            df["scraped_at"] = df["scraped_at"].dt.tz_localize(None)
            
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
    # Sidebar Filters
    st.sidebar.header(t("sidebar_filters", lang=lang))

    # Sort keywords by their absolute lowest price in the DB
    # so the cheapest GPU series (e.g. 5070) is always on the left
    keyword_min_prices = df.groupby("search_keyword")["price_cash"].min().sort_values()
    keywords = keyword_min_prices.index.tolist()
    
    selected_keywords = st.sidebar.multiselect(
        t("select_gpus", lang=lang), keywords, default=keywords, placeholder=t("choose_option", lang=lang)
    )
    # Ensure selected keywords maintain this price-based order
    selected_keywords = sorted(selected_keywords, key=lambda k: keywords.index(k))

    stores = df["store_name"].unique().tolist()
    selected_stores = st.sidebar.multiselect(t("select_stores", lang=lang), stores, default=stores, placeholder=t("choose_option", lang=lang))

    brands = df["brand"].dropna().unique().tolist()
    selected_brands = st.sidebar.multiselect(t("select_brands", lang=lang), brands, default=brands, placeholder=t("choose_option", lang=lang))

    # Apply Filters
    filtered_df = df[
        (df["search_keyword"].isin(selected_keywords))
        & (df["store_name"].isin(selected_stores))
    ]
    if selected_brands:
        filtered_df = filtered_df[filtered_df["brand"].isin(selected_brands) | filtered_df["brand"].isna()]

    if filtered_df.empty:
        st.warning(t("no_data_filters", lang=lang))
    else:
        # KPIs
        st.subheader(t("market_overview", lang=lang))
        cols = st.columns(len(selected_keywords))

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
                    kpi_col3.metric(
                        label=t("market_avg", lang=lang),
                        value=f"R$ {avg_current:,.2f}"
                    )
                    
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
                            
                        kpi_col4.metric(
                            label=t("best_inst", lang=lang),
                            value=f"R$ {best_inst['price_installments']:,.2f}",
                            delta=inst_delta_str,
                            delta_color=inst_delta_col,
                        )
                        kpi_col4.markdown(f"*{best_inst['store_name']} - {best_inst['model']}* [**{t('go_to_store', lang=lang)}**]({best_inst['product_url']})")
                    else:
                        kpi_col4.metric(t("best_inst", lang=lang), t("na", lang=lang))
        # Price Trends
        st.markdown("<br>", unsafe_allow_html=True)
        st.divider()
        st.subheader(t("price_trends", lang=lang))
        
        if selected_keywords:
            trend_cols = st.columns(len(selected_keywords))
            for idx, keyword in enumerate(selected_keywords):
                with trend_cols[idx]:
                    keyword_df = filtered_df[filtered_df["search_keyword"] == keyword]
                    if not keyword_df.empty:
                        # Plotly chart grouping by product_name and differentiating stores
                        fig = px.line(
                            keyword_df,
                            x="scraped_at",
                            y="price_cash",
                            color="product_name",
                            line_dash="store_name",
                            title=t("price_history_title", lang=lang, keyword=keyword.upper()),
                            markers=True,
                            hover_data=["search_keyword", "price_installments", "product_title"],
                            custom_data=["brand", "model", "store_name"]
                        )
                        # Allow auto-scaling but format nicely based on zoom level
                        fig.update_xaxes(
                            title_text="",
                            tickformatstops=[
                                dict(dtickrange=[None, 3600000], value="%H:%M"), 
                                dict(dtickrange=[3600000, 86400000], value="%d %b\n%H:00"), 
                                dict(dtickrange=[86400000, None], value="%d %b %Y") 
                            ]
                        )
                        # Customize hover label to show price and product details
                        fig.update_traces(
                            hovertemplate="<b>%{customdata[0]} %{customdata[1]}</b><br>Price: R$ %{y:,.2f}<br>Store: %{customdata[2]}<br>Date: %{x}<extra></extra>"
                        )
                        fig.update_layout(
                            margin=dict(l=10, r=10, t=30, b=10),
                            legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5)
                        )
                        st.plotly_chart(fig, width='stretch')
                    else:
                        st.info(t("no_trend_data", lang=lang, keyword=keyword.upper()))

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
                        col3.metric(
                            label=t("current_avg", lang=lang),
                            value=f"R$ {avg_price:,.2f}"
                        )
                        
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
                                
                            col4.metric(
                                label=t("best_inst", lang=lang),
                                value=f"R$ {best_inst['price_installments']:,.2f}",
                                delta=inst_delta_str,
                                delta_color=inst_delta_col,
                            )
                            col4.markdown(f"*{best_inst['store_name']}* [**{t('go_to_store', lang=lang)}**]({best_inst['product_url']})")
                        else:
                            col4.metric(t("best_inst", lang=lang), t("na", lang=lang))
            
                        # Detailed line chart for the selected product
                        detail_fig = px.line(
                            product_df,
                            x="scraped_at",
                            y="price_cash",
                            color="store_name",
                            title=t("price_history_title", lang=lang, keyword=""),
                            markers=True,
                            hover_data=["search_keyword", "price_installments", "product_title"]
                        )
                        detail_fig.update_traces(
                            hovertemplate="<b>"+selected_product+"</b><br>Price: R$ %{y:,.2f}<br>Store: %{customdata[0]}<br>Date: %{x}<extra></extra>",
                            customdata=product_df[["store_name"]].values
                        )
                        # Adjust layout for narrow columns
                        detail_fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
                        detail_fig.update_xaxes(
                            title_text="",
                            tickformatstops=[
                                dict(dtickrange=[None, 3600000], value="%H:%M"),
                                dict(dtickrange=[3600000, 86400000], value="%d %b"),
                                dict(dtickrange=[86400000, None], value="%d %b")
                            ]
                        )
                        st.plotly_chart(detail_fig, width='stretch')

        # Raw Data Grid
        st.markdown("<br>", unsafe_allow_html=True)
        st.divider()
        st.subheader(t("raw_data", lang=lang))
        display_df = filtered_df.copy()
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
        f_col1, f_col2 = st.columns(2)
        filter_col = f_col1.selectbox(t("select_col", lang=lang), options=["None"] + list(display_df.columns))
        if filter_col != "None":
            unique_values = display_df[filter_col].dropna().unique().tolist()
            selected_values = f_col2.multiselect(t("select_val", lang=lang, col=filter_col), options=unique_values, default=unique_values)
            display_df = display_df[display_df[filter_col].isin(selected_values) | display_df[filter_col].isna()]

        # Configure columns for better display
        st.dataframe(
            display_df,
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
