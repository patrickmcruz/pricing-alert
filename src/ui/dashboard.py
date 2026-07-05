import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px
import os

DB_PATH = os.path.join("data", "prices.db")

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

    # Apply Filters
    filtered_df = df[
        (df["search_keyword"].isin(selected_keywords))
        & (df["store_name"].isin(selected_stores))
    ]

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
        # Plotly chart grouping by store and tracking price_cash over scraped_at
        fig = px.line(
            filtered_df,
            x="scraped_at",
            y="price_cash",
            color="store_name",
            symbol="search_keyword",
            title="Cash Price History",
            markers=True,
        )
        st.plotly_chart(fig, use_container_width=True)

        # Raw Data Grid
        st.subheader("Raw Scraped Data")
        display_df = filtered_df.copy()
        display_df = display_df[
            [
                "scraped_at",
                "store_name",
                "search_keyword",
                "product_title",
                "price_cash",
                "price_installments",
                "is_available",
                "product_url",
            ]
        ]

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
