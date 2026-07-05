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
        st.subheader("Current Market Overview")
        cols = st.columns(len(selected_keywords))

        for idx, keyword in enumerate(selected_keywords):
            keyword_df = filtered_df[filtered_df["search_keyword"] == keyword]
            if not keyword_df.empty:
                # Get the absolute lowest price
                lowest = keyword_df.loc[keyword_df["price_cash"].idxmin()]
                cols[idx].metric(
                    label=f"Lowest {keyword.upper()}",
                    value=f"R$ {lowest['price_cash']:,.2f}",
                    delta=f"Store: {lowest['store_name']}",
                    delta_color="off",
                )

        # Price Trends
        st.subheader("Price Trends Over Time")
        
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
        st.subheader("Detailed Product View")
        
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
                        # Show key metrics for the selected product
                        latest = product_df.iloc[-1]
                        lowest_price = product_df["price_cash"].min()
                        highest_price = product_df["price_cash"].max()
                        avg_price = product_df["price_cash"].mean()
                        
                        std_dev = product_df["price_cash"].std()
                        st.markdown("#### Cash Analytics (À vista)")
                        col1, col2 = st.columns(2)
                        col1.metric("Current Price", f"R$ {latest['price_cash']:,.2f}")
                        col2.metric("Lowest Price", f"R$ {lowest_price:,.2f}")
                        
                        col3, col4 = st.columns(2)
                        col3.metric("Highest Price", f"R$ {highest_price:,.2f}")
                        col4.metric("Average Price", f"R$ {avg_price:,.2f}")
                        
                        # Installments Analytics
                        if "price_installments" in product_df.columns and not product_df["price_installments"].isna().all():
                            st.markdown("#### Installment Analytics")
                            lowest_inst = product_df["price_installments"].min()
                            
                            i_col1, i_col2 = st.columns(2)
                            if pd.notna(latest.get("price_installments")):
                                i_col1.metric("Current Inst.", f"R$ {latest['price_installments']:,.2f}")
                            else:
                                i_col1.metric("Current Inst.", "N/A")
                                
                            i_col2.metric("Lowest Inst.", f"R$ {lowest_inst:,.2f}")
            
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
        st.subheader("Raw Scraped Data")
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
