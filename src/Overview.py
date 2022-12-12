from typing import cast

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(layout="wide")

DEFAULT_POWER = 1.0  # mW

if True:
    from src.optimization import prepare_and_run_optimization
    from src.pages.Power_Consumption import app as power_page_app
    from src.pages.Spot_Prices import app as spot_price_page_app


def correct_spot_prices(
    spot_price_df: pd.DataFrame, tariff: str, moms: int, exposure: int, elafgift: float
) -> None:
    # TODO: implement tariffs directly in the spot price data
    spot_price_df.SpotPriceDKK += elafgift
    spot_price_df.SpotPriceDKK *= exposure / 100
    spot_price_df.SpotPriceDKK *= 1 + moms / 100


def main() -> None:
    # Simple settings
    st.sidebar.title("Settings")

    # stremlit input float number
    v = (
        DEFAULT_POWER
        if "hourly_base_power" not in st.session_state
        else st.session_state.hourly_base_power
    )
    hourly_base_power = st.sidebar.number_input(
        label="Hourly base power [mW]",
        min_value=1e-06,
        value=v,
        step=0.1,
        format="%0.3f",
    )
    prev_hourly_base_power = (
        DEFAULT_POWER
        if "hourly_base_power" not in st.session_state
        else st.session_state.hourly_base_power
    )
    st.session_state.prev_hourly_base_power = prev_hourly_base_power
    st.session_state.hourly_base_power = hourly_base_power

    # Create an instance of the app
    if "pre_run" not in st.session_state:
        st.session_state.pre_run = True
        spot_price_df = spot_price_page_app(pre_run=True)
        power_df = power_page_app(pre_run=True)
    else:
        spot_price_df = spot_price_page_app(pre_run=False, get_state=True)
        st.session_state.spot_price_df = spot_price_df
        power_df = power_page_app(pre_run=False, get_state=True)
        # st.session_state.power_df = power_df

    shiftable_hours_options = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    shiftable_hours = st.sidebar.selectbox(
        "Hours to shift", shiftable_hours_options, index=0
    )
    immediate_rebound_options = ["Delayed", "Immediate"]
    immediate_rebound = st.sidebar.selectbox(
        "Rebound", immediate_rebound_options, index=0
    )

    tariff_options = ["Radius A", "Radius B", "Radius C", "N1 A", "N1 B", "N1 C"]
    tariff = st.sidebar.selectbox("Tariff", tariff_options, index=0)
    moms_options = [0, 25]
    moms = st.sidebar.selectbox("VAT [%]", moms_options, index=0)
    elafgift_options = [0.0, 0.76]
    elafgift = st.sidebar.selectbox("Tax DKK/kWh", elafgift_options, index=0)
    exposure_options = [50, 100]
    exposure = st.sidebar.selectbox(
        "Exposure to spot price [%]", exposure_options, index=1
    )
    correct_spot_prices(
        spot_price_df,
        cast(str, tariff),
        cast(int, moms),
        cast(int, exposure),
        cast(float, elafgift),
    )

    opt_result, fig = prepare_and_run_optimization(
        spot_price_df,
        power_df,
        cast(int, shiftable_hours),
        cast(str, immediate_rebound),
        st.session_state.hourly_base_power,
    )

    st.title("Potential summary")
    st.write("")

    base_cost = sum(opt_result.base_cost.reshape(-1))
    shifted_cost = sum(opt_result.mem_cost.reshape(-1))
    savings = (base_cost - shifted_cost) / base_cost * 100

    st.write(
        f"Number of days considered in optimization: {int(spot_price_df.shape[0] / 24)} days"
    )

    st.write(f"Base cost: {base_cost:,.0f} DKK")
    st.write(f"Cost with load shifting: {shifted_cost:,.0f} DKK")
    st.write(f"Savings: {savings:.2f} %")

    if np.isclose(savings, 0.0):
        st.write("OBS: It is not possible to shift load with chosen settings")

    st.info(
        "💡 The plots below are zoomed in to show 24 hours only. Press 'Autoscale' to zoom out (upper right corner)."
    )

    st.plotly_chart(fig, use_container_width=True, height=700)

    st.session_state.pre_run = False


main()
