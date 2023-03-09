import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from st_aggrid import AgGrid
from st_aggrid.grid_options_builder import GridOptionsBuilder


# @st.cache
def read_power_data() -> pd.DataFrame:
    STATE = st.session_state.state
    # create dataframe with 24 hours as index and all weekdays as columns with values of hourly_base_power
    power = pd.DataFrame(
        np.ones((24, 7)) * STATE["hourly_base_power"],
        index=list(range(1, 25)),
        columns=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    ).reset_index()
    power = power.rename(columns={"index": "Hour"})
    return power


def initialize_power_data() -> None:
    STATE = st.session_state.state
    print("Pre-run: getting default power consumption...")
    STATE["power_df"] = read_power_data()
    STATE["intermediate_power_df"] = STATE["power_df"].copy()


def get_power_data() -> pd.DataFrame:

    power = read_power_data()
    STATE = st.session_state.state

    if STATE.get("reset_power", False):
        print("Resetting power consumption to default values")
        STATE["power_df"] = power.copy()
        STATE["intermediate_power_df"] = power.copy()
        STATE["reset_power"] = False
        # NOTE: changing dtype of Hour to int is necessary for the AgGrid to work properly
        power.Hour = power.Hour.astype(float)
    else:
        # change power values according to selection
        ix = STATE["power_df"].set_index("Hour").index - 1
        cix = STATE["power_df"].columns
        power.loc[ix, cix] = STATE["power_df"].values.copy()
        # NOTE: changing dtype of Hour to int is necessary for the AgGrid to work properly
        power.Hour = power.Hour.astype(int)

    return power


def app() -> None:

    STATE = st.session_state.state

    # TODO: investigate caching error from 'read_power_data'

    st.title("Specify power consumption")
    st.write("")
    st.markdown(
        """
           Change the consumption for each hour and day to create a more accurate flexibility estimation
           Monday's prices are used as default if chosen spot prices are for one day only.
        """
    )
    st.write("")
    st.write("")

    st.info("💡 Select eligible hours by clicking the checkbox.")
    st.info(
        "💡 Select eligible days by pressing 'columns' and selecting days accordingly."
    )
    st.info("💡 Double click on cell and change consumption by pressing 'enter'.")
    st.info("💡 Press 'Save power consumption' when finished and go back to 'Overview'.")
    st.caption("")

    power = get_power_data()
    gd = GridOptionsBuilder.from_dataframe(power)
    gd.configure_pagination(paginationAutoPageSize=True)  # Add pagination
    gd.configure_side_bar()  # Add a sidebar
    gd.configure_default_column(editable=True)
    gd.configure_column("Hour", editable=False)
    gd.configure_selection(
        "multiple",
        use_checkbox=True,
        groupSelectsChildren="Group checkbox select children",
    )  # Enable multi-row selection
    gridOptions = gd.build()

    grid_response = AgGrid(
        power,
        gridOptions=gridOptions,
        data_return_mode="FILTERED_AND_SORTED",
        update_on=[
            "paginationChanged",
            "MODEL_CHANGED",
            "columnVisible",
        ],
        fit_columns_on_grid_load=False,
        enable_enterprise_modules=True,
        height=350,
        width="100%",
        # reload_data=True,
    )

    st.write("")

    power = grid_response["data"]
    selected_rows = grid_response["selected_rows"]

    # print(selected_rows)

    selected_columns = (
        [c["colId"] for c in grid_response["column_state"] if not c["hide"]]
        if grid_response.get("column_state")
        else power.columns.tolist()  # type: ignore
    )

    if not pd.DataFrame(selected_rows).empty:
        power = pd.DataFrame(selected_rows)[selected_columns]
    else:
        power = power[selected_columns]  # type: ignore

    # print(power)

    STATE["intermediate_power_df"] = power.copy()

    STATE["reset_power"] = st.sidebar.button("Reset power consumption to default")
    STATE["save_power"] = st.sidebar.button("Save power consumption profile")

    if STATE["reset_power"]:
        STATE["power_df"] = read_power_data()
        STATE["intermediate_power_df"] = STATE["power_df"].copy()
        STATE["reset_power"] = False

    if STATE["save_power"]:
        print("Saving power consumption profile...")
        STATE["power_df"] = STATE["intermediate_power_df"].copy()
        STATE["save_power"] = False

    def create_power_plot() -> None:
        fig = make_subplots(
            rows=1,
            cols=2,
            subplot_titles=("Chosen power", "Saved power"),
        )
        cols = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for c in cols:
            if c in power.columns:
                fig.add_trace(
                    go.Scatter(
                        x=power["Hour"],
                        y=power[c],
                        mode="lines+markers",
                        name=f"1-{c}",
                        line_shape="vh",
                        opacity=0.5,
                    ),
                    row=1,
                    col=1,
                )
            if c in STATE["power_df"].columns:
                fig.add_trace(
                    go.Scatter(
                        x=STATE["power_df"]["Hour"],
                        y=STATE["power_df"][c],
                        mode="lines+markers",
                        name=f"2-{c}",
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
                title="Hour",
            ),
            xaxis2=dict(
                title="Hour",
            ),
            yaxis1=dict(
                title="Power [MW]",
            ),
            yaxis2=dict(
                title="Power [MW]",
            ),
        )

        st.plotly_chart(fig, use_container_width=True, width=800, height=500)

    # st.info("OBS: only the values inputed in the previous selection are saved")

    create_power_plot()


if "state" in st.session_state and "initialized" in st.session_state.state:
    app()
else:
    st.write(
        "It seems you have refreshed the page. Please go back to 'Overview' and start again."
    )
