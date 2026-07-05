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

DB_PATH = settings.db_path

st.set_page_config(page_title="GPU Price Tracker", layout="wide")

st.title("GPU Price Tracker Dashboard")
st.markdown(
    "Track GeForce RTX 5070 and RTX 5070 Ti prices across Brazilian e-commerce stores."
)


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
    st.info(
        "No pricing data found in the database. Please ensure the orchestrator is running."
    )
else:
    # Sidebar Filters
    st.sidebar.header("Filters")

    # Sort keywords by their absolute lowest price in the DB
    # so the cheapest GPU series (e.g. 5070) is always on the left
    keyword_min_prices = df.groupby("search_keyword")["price_cash"].min().sort_values()
    keywords = keyword_min_prices.index.tolist()
    
    selected_keywords = st.sidebar.multiselect(
        "Select GPUs", keywords, default=keywords
    )
    # Ensure selected keywords maintain this price-based order
    selected_keywords = sorted(selected_keywords, key=lambda k: keywords.index(k))

    stores = df["store_name"].unique().tolist()
    selected_stores = st.sidebar.multiselect("Select Stores", stores, default=stores)

    brands = df["brand"].dropna().unique().tolist()
    selected_brands = st.sidebar.multiselect("Select Brands", brands, default=brands)

    # Apply Filters
    filtered_df = df[
        (df["search_keyword"].isin(selected_keywords))
        & (df["store_name"].isin(selected_stores))
    ]
    if selected_brands:
        filtered_df = filtered_df[filtered_df["brand"].isin(selected_brands) | filtered_df["brand"].isna()]

    if filtered_df.empty:
        st.warning("No data matches the selected filters.")
    else:
        # KPIs
        st.subheader("🌐 Current Market Overview")
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
                    
                    st.markdown(f"**{keyword.upper()} Market**")
                    
                    kpi_col1, kpi_col2 = st.columns(2)
                    
                    # Diff vs Historical
                    diff_from_hist = best_current['price_cash'] - best_historical['price_cash']
                    if diff_from_hist == 0:
                        delta_str = "Matches All-Time Low!"
                        delta_col = "normal"
                    else:
                        delta_str = f"+ R$ {diff_from_hist:,.2f} vs Low"
                        delta_col = "inverse" # Red means higher than historical low
                        
                    kpi_col1.metric(
                        label="🏆 Best Deal Right Now",
                        value=f"R$ {best_current['price_cash']:,.2f}",
                        delta=delta_str,
                        delta_color=delta_col,
                    )
                    kpi_col1.markdown(f"*{best_current['store_name']} - {best_current['model']}* [**↗️**]({best_current['product_url']})")
                    
                    kpi_col2.metric(
                        label="📉 All-Time Low",
                        value=f"R$ {best_historical['price_cash']:,.2f}"
                    )
                    
                    kpi_col3, kpi_col4 = st.columns(2)
                    kpi_col3.metric(
                        label="📊 Market Average",
                        value=f"R$ {avg_current:,.2f}"
                    )
                    
                    if "price_installments" in current_market.columns and not current_market["price_installments"].isna().all():
                        best_inst_idx = current_market["price_installments"].idxmin()
                        best_inst = current_market.loc[best_inst_idx]
                        kpi_col4.metric(
                            label="💳 Best Installment",
                            value=f"R$ {best_inst['price_installments']:,.2f}",
                        )
                        kpi_col4.markdown(f"*{best_inst['store_name']} - {best_inst['model']}* [**↗️**]({best_inst['product_url']})")
                    else:
                        kpi_col4.metric("💳 Best Installment", "N/A")
        # Price Trends
        st.markdown("<br>", unsafe_allow_html=True)
        st.divider()
        st.subheader("📈 Price Trends Over Time")
        
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
                            title=f"{keyword.upper()} Price History",
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
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info(f"No trend data for {keyword.upper()}")

        # ----- Detailed Product View -----
        st.markdown("<br>", unsafe_allow_html=True)
        st.divider()
        st.subheader("🔍 Detailed Product View")
        
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
                    selected_product = st.selectbox(f"Select Model", product_options, index=0, key=f"select_{keyword}")
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
                        
                        st.markdown("#### Analytics")
                        col1, col2 = st.columns(2)
                        
                        # Diff vs Historical
                        diff_from_hist = best_current['price_cash'] - lowest_price
                        if diff_from_hist == 0:
                            delta_str = "Matches All-Time Low!"
                            delta_col = "normal"
                        else:
                            delta_str = f"+ R$ {diff_from_hist:,.2f} vs Low"
                            delta_col = "inverse"
                            
                        col1.metric(
                            label="🏆 Current Best Price",
                            value=f"R$ {best_current['price_cash']:,.2f}",
                            delta=delta_str,
                            delta_color=delta_col,
                        )
                        col1.markdown(f"*{best_current['store_name']}* [**↗️**]({best_current['product_url']})")
                        
                        col2.metric(
                            label="📉 All-Time Low",
                            value=f"R$ {lowest_price:,.2f}"
                        )
                        
                        col3, col4 = st.columns(2)
                        col3.metric(
                            label="📊 Current Average",
                            value=f"R$ {avg_price:,.2f}"
                        )
                        
                        if "price_installments" in current_prod_market.columns and not current_prod_market["price_installments"].isna().all():
                            best_inst_idx = current_prod_market["price_installments"].idxmin()
                            best_inst = current_prod_market.loc[best_inst_idx]
                            col4.metric(
                                label="💳 Best Installment",
                                value=f"R$ {best_inst['price_installments']:,.2f}",
                            )
                            col4.markdown(f"*{best_inst['store_name']}* [**↗️**]({best_inst['product_url']})")
                        else:
                            col4.metric("💳 Best Installment", "N/A")
            
                        # Detailed line chart for the selected product
                        detail_fig = px.line(
                            product_df,
                            x="scraped_at",
                            y="price_cash",
                            color="store_name",
                            title=f"Price History",
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
                        st.plotly_chart(detail_fig, use_container_width=True)

        # Raw Data Grid
        st.markdown("<br>", unsafe_allow_html=True)
        st.divider()
        st.subheader("🗄️ Raw Scraped Data")
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

        st.markdown("**Filter Raw Data**")
        f_col1, f_col2 = st.columns(2)
        filter_col = f_col1.selectbox("Select column to filter", options=["None"] + list(display_df.columns))
        if filter_col != "None":
            unique_values = display_df[filter_col].dropna().unique().tolist()
            selected_values = f_col2.multiselect(f"Select values for '{filter_col}'", options=unique_values, default=unique_values)
            display_df = display_df[display_df[filter_col].isin(selected_values) | display_df[filter_col].isna()]

        # Configure columns for better display
        st.dataframe(
            display_df,
            column_config={
                "product_url": st.column_config.LinkColumn(
                    "Product Link",
                    display_text=r"(.*)"
                ),
                "scraped_at": st.column_config.DatetimeColumn(
                    "Scraped At", format="YYYY-MM-DD HH:mm:ss"
                ),
                "price_cash": st.column_config.NumberColumn(
                    "Price (Cash)", format="R$ %.2f"
                ),
                "price_installments": st.column_config.NumberColumn(
                    "Price (Inst.)", format="R$ %.2f"
                ),
            },
            hide_index=True,
            use_container_width=True,
        )
