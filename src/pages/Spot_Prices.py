from typing import cast

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

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


def get_pre_run_case() -> pd.DataFrame:
    spot = read_spot_price_data()

    year = 2022
    area = "DK1"

    spot_area_time = spot.query(f"PriceArea == '{area}' & HourUTC.dt.year == {year}")

    return spot_area_time


def app(pre_run: bool = False, get_state: bool = False) -> pd.DataFrame:

    if pre_run:
        print("Pre-run: getting default spot prices...")
        st.session_state.pre_run = True
        st.session_state.spot_area_time = get_pre_run_case()
        st.session_state.pre_run = False
        return st.session_state.spot_area_time
    elif pre_run is False and get_state:
        assert "spot_area_time" in st.session_state, "Spot prices must be specified"
        return st.session_state.spot_area_time
    elif pre_run and get_state:
        raise ValueError("Pre-run and get_state cannot be True at the same time")
    else:
        pass

    spot = read_spot_price_data()
    area_options = ["DK1", "DK2"]
    resolution_options = ["yearly", "daily"]
    year_options = [2021, 2022]
    month_options = list(MONTH_TO_INT.keys())

    # Title of the main page
    st.title("Selection of spot price data")

    st.info(
        "💡 Choose spot price data in the sidebar and go back to 'Overview' when done."
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

    placeholder_spot_price_plot = st.empty()

    def create_spot_price_plot() -> None:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=spot_area_time.HourUTC,
                y=spot_area_time.SpotPriceDKK,
                mode="lines",
                name="DKK",
                line_shape="vh",
            )
        )
        fig.update_layout(
            title="Spot prices",
            xaxis_title="Time",
            yaxis_title="Price [DKK]",
            legend_title="Legend Title",
            font=dict(
                family="Courier New, monospace",
                size=18,
                color="#7f7f7f",
            ),
        )

        placeholder_spot_price_plot.write(fig)

    create_spot_price_plot()

    st.session_state.spot_area_time = spot_area_time

    return spot_area_time


if "pre_run" in st.session_state and not st.session_state.pre_run:
    app(pre_run=False)
