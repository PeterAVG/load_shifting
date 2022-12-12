from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from st_aggrid import AgGrid
from st_aggrid.grid_options_builder import GridOptionsBuilder


# @st.cache
def read_power_data() -> pd.DataFrame:
    # create dataframe with 24 hours as index and all weekdays as columns with values of hourly_base_power
    power = pd.DataFrame(
        np.ones((24, 7)) * st.session_state.hourly_base_power,
        index=list(range(1, 25)),
        columns=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    ).reset_index()
    power = power.rename(columns={"index": "Hour"})
    return power


def get_power_data() -> pd.DataFrame:
    power = read_power_data()

    if not st.session_state.pre_run and not st.session_state.reset_power_consumption:
        # change power values according to selection
        ix = st.session_state.power.set_index("Hour").index - 1
        cix = st.session_state.power.columns
        power.loc[ix, cix] = st.session_state.power.values.copy()
        power.Hour = power.Hour.astype(int)
    else:
        print("Resetting power consumption to default values")
        st.session_state.power = power.copy()
        st.session_state.changed_power = power.copy()
        st.session_state.reset_power_consumption = False

        # NOTE: changing dtype of Hour to int is necessary for the AgGrid to work properly
        power.Hour = power.Hour.astype(float)

    return power


def app(
    pre_run: bool = False,
    get_state: bool = False,
    power: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:

    # TODO: investigate caching error from 'read_power_data'

    if pre_run:
        print("Pre-run: getting default power consumption...")
        st.session_state.pre_run = True
        st.session_state.power = read_power_data()
        st.session_state.pre_run = False
        return st.session_state.power.copy()
    elif pre_run is False and get_state:
        assert "power" in st.session_state, "power must be specified"
        cols = st.session_state.power.columns.drop("Hour")
        to_replace = st.session_state.prev_hourly_base_power
        replace_with = st.session_state.hourly_base_power
        st.session_state.power.replace(
            {c: to_replace for c in cols}, replace_with, inplace=True
        )
        return st.session_state.power.copy()
    elif pre_run is False and not get_state:
        assert power is not None, "power must be specified"
    elif pre_run and get_state:
        raise ValueError("Pre-run and get_state cannot be True at the same time")
    else:
        pass

    if st.session_state.customize_power == "Yes":

        st.title("Specify power consumption")
        st.write("")
        st.markdown(
            """Change the consumption for each hour to create a more accurate flexibility estimation"""
        )
        st.markdown(
            """OBS: for a daily optimization, only change Monday's consumption."""
        )
        st.write("")
        st.write("")
        # st.subheader("① Edit and select cells")
        st.info("💡 Select eligible hours by clicking the checkbox.")
        st.info(
            "💡 Select eligible days by pressing 'columns' and selecting days accordingly."
        )
        st.info("💡 Double click on cell and change consumption by pressing 'enter'.")
        st.info("💡 Press 'Save power consumption' when finished.")
        st.caption("")

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
        print(selected_rows)
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

    placeholder_power_plot = st.empty()

    def create_power_plot(power: pd.DataFrame) -> None:
        cols = power.drop(columns=["Hour"]).columns.tolist()
        fig = go.Figure()
        for c in cols:
            fig.add_trace(
                go.Scatter(
                    x=power["Hour"],
                    y=power[c],
                    mode="lines+markers",
                    name=c,
                    line_shape="vh",
                )
            )
        fig.update_layout(
            title="Hourly power consumption [kW]",
            xaxis_title="Hour",
            yaxis_title="Power [kW]",
            legend_title="Legend Title",
            font=dict(
                family="Courier New, monospace",
                size=18,
                color="#7f7f7f",
            ),
        )

        placeholder_power_plot.write(fig)

    st.info("OBS: only the values inputed in the previous selection are saved")

    if st.session_state.customize_power == "Yes":
        create_power_plot(power)

    return power


if "pre_run" in st.session_state and not st.session_state.pre_run:
    # this code only runs when user is navigating between pages

    customize_power = st.sidebar.selectbox(
        "Customize power consumption:", ("Yes", "No"), index=0
    )
    st.session_state.customize_power = customize_power

    if customize_power == "Yes":

        reset_power_consumption = st.sidebar.button(
            "Reset power consumption to default"
        )
        st.session_state.reset_power_consumption = reset_power_consumption

        save_power_consumption = st.sidebar.button("Save power consumption")
        st.session_state.save_power_consumption = save_power_consumption

    # In this situation, the user is specifying the power consumption
    # and we want to use the values previously specified
    if (
        "save_power_consumption" in st.session_state
        and st.session_state.save_power_consumption
        and not st.session_state.get("prev_save_power_consumption", False)
    ):
        assert "power" in st.session_state, "power must be specified"
        st.session_state.power = st.session_state.changed_power.copy()
        st.session_state.save_power_consumption = False
        st.session_state.prev_save_power_consumption = True

        st.write(
            "Power consumption saved... Return to overview page to continue"
            " or click 'Power Consumption' to make additional changes."
        )
    else:
        power = get_power_data()
        new_power = app(pre_run=False, get_state=False, power=power)
        st.session_state.changed_power = new_power.copy()
        st.session_state.prev_save_power_consumption = False
