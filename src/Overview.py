from typing import Any, Dict, cast

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(layout="wide")


DEFAULT_POWER = 1.0  # mW

if True:
    from src.optimization import prepare_and_run_optimization
    from src.pages.Power_Consumption import initialize_power_data
    from src.pages.Spot_Prices import initialize_spot_price_data

if "state" not in st.session_state:
    print("\n\nInitializing session state...")
    st.session_state.state: Dict[str, Any] = {}  # type: ignore

STATE = st.session_state.state


def correct_spot_prices(
    spot_price_df: pd.DataFrame, tariff: str, moms: int, exposure: int, elafgift: float
) -> None:
    # TODO: implement tariffs directly in the spot price data
    spot_price_df.SpotPriceDKK += elafgift
    spot_price_df.SpotPriceDKK *= exposure / 100
    spot_price_df.SpotPriceDKK *= 1 + moms / 100


def update_power_data() -> None:
    assert "power_df" in STATE
    cols = STATE["power_df"].columns.drop("Hour")
    to_replace = STATE["prev_hourly_base_power"]
    replace_with = STATE["hourly_base_power"]
    STATE["power_df"].replace({c: to_replace for c in cols}, replace_with, inplace=True)


def main() -> None:
    # Simple settings
    st.sidebar.title("Settings")

    help_text = "Baseline power usage in all hours unless customized in the page, 'Power Consumption'."
    hourly_base_power = st.sidebar.number_input(
        label="Hourly base power [mW]",
        min_value=1e-06,
        value=DEFAULT_POWER,
        step=0.1,
        format="%0.3f",
        help=help_text,
    )

    STATE["prev_hourly_base_power"] = STATE.get("hourly_base_power", DEFAULT_POWER)
    STATE["hourly_base_power"] = hourly_base_power

    if STATE["prev_hourly_base_power"] != STATE["hourly_base_power"]:
        update_power_data()

    # Create an instance of the app
    if "initialized" not in STATE:
        initialize_spot_price_data()
        initialize_power_data()
        assert "spot_price_df" in STATE
        assert "power_df" in STATE
        STATE["initialized"] = True
    else:
        assert STATE["initialized"]
        assert "spot_price_df" in STATE
        assert "power_df" in STATE
        # spot_price_page_app(get_state=True)
        # power_page_app(get_state=True)

    help_text = "Percentage of how much of your power consumption that is flexible."
    percent_flexible = st.sidebar.number_input(
        label="Flexibility potential [%]",
        min_value=0,
        max_value=100,
        value=100,
        step=10,
        # format="%0.3f",
        help=help_text,
    )

    shiftable_hours_options = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    help_text = "Number of hours to shift load. E.g. 2 means that the load can be shifted 2 hours."
    shiftable_hours = st.sidebar.selectbox(
        "Hours to shift", shiftable_hours_options, index=0, help=help_text
    )
    help_text = "Whether rebound occurs immediately before or after a load shift - or at any given time. 'Delayed' yields a better result."
    immediate_rebound_options = ["Delayed", "Immediate"]
    immediate_rebound = st.sidebar.selectbox(
        "Rebound", immediate_rebound_options, index=0, help=help_text
    )

    # tariff_options = ["Radius A", "Radius B", "Radius C", "N1 A", "N1 B", "N1 C"]
    # tariff = st.sidebar.selectbox("Tariff", tariff_options, index=0)
    tariff = ""
    moms_options = [0, 25]
    moms = st.sidebar.selectbox("VAT [%]", moms_options, index=0)
    elafgift_options = [0.0, 0.76]
    elafgift = st.sidebar.selectbox("Tax DKK/kWh", elafgift_options, index=0)
    help_text = "Exposure at 100% means that the spot price is used as is. Exposure at 50% means that the spot price is halved."
    exposure_options = [50, 100]
    exposure = st.sidebar.selectbox(
        "Exposure to spot price [%]", exposure_options, index=1, help=help_text
    )
    correct_spot_prices(
        cast(pd.DataFrame, STATE["spot_price_df"]),
        cast(str, tariff),
        cast(int, moms),
        cast(int, exposure),
        cast(float, elafgift),
    )

    opt_result, fig = prepare_and_run_optimization(
        STATE["spot_price_df"],
        STATE["power_df"],
        cast(int, shiftable_hours),
        cast(str, immediate_rebound),
        STATE["hourly_base_power"],
        percent_flexible / 100,
    )

    st.title("Potential summary")
    st.info(
        "💡 Go to 'Power Consumption' to change which days and hours are eligable for flexibility."
    )
    st.info(
        "💡 Go to 'Spot Price' to change which spot price data to use. Default is all of 2022."
    )
    st.write("")

    base_cost = sum(opt_result.base_cost.reshape(-1))
    shifted_cost = sum(opt_result.mem_cost.reshape(-1))
    savings = (base_cost - shifted_cost) / base_cost * 100

    st.write(
        f"Number of days considered in optimization: {int(STATE['spot_price_df'].shape[0] / 24)} day(s)"
    )

    st.write(f"Base cost: {base_cost:,.0f} DKK")
    st.write(f"Cost with load shifting: {shifted_cost:,.0f} DKK")
    st.write(f"Savings: {savings:.2f} %")

    if np.isclose(savings, 0.0):
        st.write("OBS: It is not possible to shift load with chosen settings")

    st.plotly_chart(fig, use_container_width=True, height=700)
    st.info(
        "💡 The plots are zoomed in to show 24 hours only. Press 'Autoscale' to zoom out (upper right corner)."
    )


main()
