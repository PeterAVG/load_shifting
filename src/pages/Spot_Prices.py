from typing import cast

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

MONTH_TO_INT = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}


@st.cache
def read_spot_price_data() -> pd.DataFrame:
    file = "src/data/elspotprices.csv"
    spot = pd.read_csv(
        file, sep=";", decimal=",", parse_dates=["HourUTC", "HourDK"]
    ).sort_values(by="HourUTC")
    spot["Date"] = spot.HourUTC.dt.date
    dates_to_substract = (  # noqa
        spot.query("PriceArea == 'DK1'")
        .groupby("Date")
        .SpotPriceDKK.count()
        .to_frame()
        .query("SpotPriceDKK <= 23")
        .index.values.tolist()
    )
    spot = spot.query("Date != @dates_to_substract")
    spot = spot[["HourUTC", "PriceArea", "SpotPriceDKK", "Date"]]
    spot["SpotPriceDKK"] = spot["SpotPriceDKK"].values  # type:ignore

    print(spot.shape)

    return spot


def initialize_spot_price_data() -> None:
    print("Pre-run: getting default spot prices...")

    spot = read_spot_price_data()
    year = 2022
    area = "DK1"

    # STATE["original_spot_price_df"] = spot.copy()
    # STATE = st.session_state.state
    st.session_state.state["spot_price_df"] = spot.query(
        f"PriceArea == '{area}' & HourUTC.dt.year == {year}"
    ).copy()


def app() -> None:

    STATE = st.session_state.state

    spot = read_spot_price_data()
    area_options = ["DK1", "DK2"]
    resolution_options = ["yearly", "daily"]
    year_options = [2021, 2022, 2023]
    month_options = list(MONTH_TO_INT.keys())

    # Title of the main page
    st.title("Selection of spot price data")

    st.info(
        "💡 Choose desired spot price data in the sidebar, click 'Save spot prices', and go back to 'Overview' when finished."
    )

    area = st.sidebar.selectbox("Select market area:", area_options, index=0)  # noqa
    spot_area = spot.query("PriceArea == @area")

    resolution = st.sidebar.selectbox("Select resolution:", resolution_options, index=0)

    if resolution == "yearly":
        year = st.sidebar.selectbox("Select year:", year_options, index=1)
        spot_area_time = spot_area.query("HourUTC.dt.year == @year")
    elif resolution == "monthly":
        # year = st.sidebar.selectbox("Select year:", year_options)
        # month = st.sidebar.selectbox("Select month:", month_options)
        # month_int = MONTH_TO_INT[month]
        # spot_area_time = spot_area.query(
        #     "HourUTC.dt.year == @year & HourUTC.dt.month == @month_int"
        # )
        raise NotImplementedError("Monthly resolution not implemented yet")
    elif resolution == "daily":
        year = st.sidebar.selectbox("Select year:", year_options)  # noqa
        month = st.sidebar.selectbox("Select month:", month_options)
        month_int = MONTH_TO_INT[cast(str, month)]  # noqa
        spot_area_time = spot_area.query(
            "HourUTC.dt.year == @year & HourUTC.dt.month == @month_int"
        )
        date_options = spot_area_time.Date.tolist()
        date = st.sidebar.date_input(  # noqa
            "Select date:",
            value=date_options[0],
            min_value=date_options[0],
            max_value=date_options[-1],
        )
        spot_area_time = spot_area.query("Date == @date")
    else:
        raise ValueError(f"Unknown resolution: {resolution}")

    STATE["reset_spot_prices"] = st.sidebar.button("Reset spot prices to default")
    STATE["save_spot_prices"] = st.sidebar.button("Save spot prices")

    if STATE["reset_spot_prices"]:
        STATE["spot_price_df"] = read_spot_price_data()
        STATE["reset_spot_prices"] = False

    if STATE["save_spot_prices"]:
        print("Saving chosen spot prices...")
        STATE["spot_price_df"] = spot_area_time
        STATE["save_spot_prices"] = False

    def create_spot_price_plot() -> None:
        fig = make_subplots(
            rows=1,
            cols=2,
            subplot_titles=("Chosen spot price", "Saved spot price"),
        )
        fig.add_trace(
            go.Scatter(
                x=spot_area_time.HourUTC,
                y=spot_area_time.SpotPriceDKK,
                mode="lines",
                name="Chosen",
                line_shape="vh",
                opacity=0.5,
            ),
            row=1,
            col=1,
        )
        saved = (
            STATE["spot_price_df"].copy()
            if "spot_price_df" in STATE
            else spot_area_time
        )
        fig.add_trace(
            go.Scatter(
                x=saved.HourUTC,
                y=saved.SpotPriceDKK,
                mode="lines",
                name="Saved",
                line_shape="vh",
            ),
            row=1,
            col=2,
        )
        fig.update_layout(
            width=800,
            height=500,
            font=dict(
                family="Courier New, monospace",
                size=18,
                color="#7f7f7f",
            ),
            xaxis1=dict(
                title="Time",
            ),
            xaxis2=dict(
                title="Time",
            ),
            yaxis1=dict(
                title="DKK/MWh",
            ),
            yaxis2=dict(
                title="DKK/MWh",
            ),
        )

        st.plotly_chart(fig, use_container_width=True, width=800, height=500)

    create_spot_price_plot()


if "state" in st.session_state and "initialized" in st.session_state.state:
    app()
else:
    st.write(
        "It seems you have refreshed the page. Please go back to 'Overview' and start again."
    )
