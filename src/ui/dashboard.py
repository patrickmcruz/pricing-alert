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

    keywords = df["search_keyword"].unique().tolist()
    selected_keywords = st.sidebar.multiselect(
        "Select GPUs", keywords, default=keywords
    )

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
        
        # Plotly chart grouping by product_name and differentiating stores
        fig = px.line(
            filtered_df,
            x="scraped_at",
            y="price_cash",
            color="product_name",
            line_dash="store_name",
            title="Cash Price History by Model & Store",
            markers=True,
            hover_data=["search_keyword", "price_installments", "product_title"],
            custom_data=["brand", "model", "store_name"]
        )
        # Allow auto-scaling but format nicely based on zoom level
        fig.update_xaxes(
            title_text="Date / Time",
            tickformatstops=[
                dict(dtickrange=[None, 3600000], value="%H:%M:%S"),  # zoom in: show minutes/seconds
                dict(dtickrange=[3600000, 86400000], value="%d %b\n%H:00"), # default zoom out: hour-by-hour
                dict(dtickrange=[86400000, None], value="%d %b %Y") # far zoom out: daily
            ]
        )
        # Customize hover label to show price and product details
        fig.update_traces(
            hovertemplate="<b>%{customdata[0]} %{customdata[1]}</b><br>Price: R$ %{y:,.2f}<br>Store: %{customdata[2]}<br>Date: %{x}<extra></extra>"
        )
        st.plotly_chart(fig, width='stretch')

        # ----- Detailed Product View -----
        st.subheader("Detailed Product View")
        # Let user pick a single product from the filtered set
        product_options = filtered_df["product_name"].unique().tolist()
        selected_product = st.selectbox("Select a product for deep analysis", product_options, index=0)
        product_df = filtered_df[filtered_df["product_name"] == selected_product].sort_values(by="scraped_at")
        if not product_df.empty:
            # Show key metrics for the selected product
            latest = product_df.iloc[-1]
            lowest_price = product_df["price_cash"].min()
            highest_price = product_df["price_cash"].max()
            avg_price = product_df["price_cash"].mean()
            
            # Since first record
            price_change_first = ((latest["price_cash"] - product_df.iloc[0]["price_cash"]) / product_df.iloc[0]["price_cash"]) * 100 if product_df.iloc[0]["price_cash"] else 0
            
            # Since last record
            if len(product_df) > 1:
                previous = product_df.iloc[-2]
                price_change_last = ((latest["price_cash"] - previous["price_cash"]) / previous["price_cash"]) * 100 if previous["price_cash"] else 0
            else:
                price_change_last = 0.0
                
            std_dev = product_df["price_cash"].std()
            col1, col2, col3 = st.columns(3)
            col1.metric("Current Price", f"R$ {latest['price_cash']:,.2f}")
            col2.metric("Lowest Price", f"R$ {lowest_price:,.2f}")
            col3.metric("Highest Price", f"R$ {highest_price:,.2f}")
            
            col4, col5, col6, col7 = st.columns(4)
            col4.metric("Average Price", f"R$ {avg_price:,.2f}")
            col5.metric("Change Since First", f"{price_change_first:.2f}%")
            col6.metric("Change Since Last", f"{price_change_last:.2f}%")
            col7.metric("Volatility (Std Dev)", f"R$ {std_dev:,.2f}" if pd.notna(std_dev) else "R$ 0.00")

            # Detailed line chart for the selected product
            detail_fig = px.line(
                product_df,
                x="scraped_at",
                y="price_cash",
                color="store_name",
                title=f"Price History for {selected_product}",
                markers=True,
                hover_data=["search_keyword", "price_installments", "product_title"]
            )
            detail_fig.update_traces(
                hovertemplate="<b>"+selected_product+"</b><br>Price: R$ %{y:,.2f}<br>Store: %{customdata[0]}<br>Date: %{x}<extra></extra>",
                customdata=product_df[["store_name"]].values
            )
            # Allow auto-scaling but format nicely based on zoom level
            detail_fig.update_xaxes(
                title_text="Date / Time",
                tickformatstops=[
                    dict(dtickrange=[None, 3600000], value="%H:%M:%S"),
                    dict(dtickrange=[3600000, 86400000], value="%d %b\n%H:00"),
                    dict(dtickrange=[86400000, None], value="%d %b %Y")
                ]
            )
            st.plotly_chart(detail_fig, width='stretch')
        else:
            st.warning("No data available for the selected product.")

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
                "discount",
                "parser_version",
                "is_available",
                "product_url",
            ]
        ]

        with st.expander("Filter Raw Data"):
            filter_col = st.selectbox("Select column to filter", options=["None"] + list(display_df.columns))
            if filter_col != "None":
                unique_values = display_df[filter_col].dropna().unique().tolist()
                selected_values = st.multiselect(f"Select values for '{filter_col}'", options=unique_values, default=unique_values)
                display_df = display_df[display_df[filter_col].isin(selected_values) | display_df[filter_col].isna()]

        # Configure columns for better display
        st.dataframe(
            display_df,
            column_config={
                "product_url": st.column_config.LinkColumn("Product Link"),
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
