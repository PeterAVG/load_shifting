from dataclasses import dataclass
from datetime import timedelta
from typing import Any, List, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.utils import timing


@dataclass
class OptimizationResult:
    base_cost: np.ndarray
    mem_cost: np.ndarray
    mem_power: np.ndarray


@timing()
def run_optimization(
    spot_price: np.ndarray,
    base_power: np.ndarray,
    shiftable_hours: int,
    immediate_rebound: bool,
    hourly_base_power: float,
    percent_flexible: float,
    shifted_load_percentage: float,
) -> OptimizationResult:
    """
    args:
        - spot_prices: 2D array of spot prices (day x hour)
        - base_power: 2D array of power consumption (day x hour)
        - shiftable_hours: hours allowed to shift
        - immediate_rebound: whether rebound happens immediately or not (either consecutive up/down or down/up)
        - hourly_base_power: default base power consumption
        - percent_flexible: percentage of power consumption that is allowed to be shifted
        - shifted_load_percentage (0-1): percentage of foregone load that is shifted

    We assume spot price optimization (load shifting) has the following contraints:
        - There is an immediate load shift (no ramping up/down)
        - Immediate or delayed rebound to original consumption after down/up-regulation
        - An action is either up-regulation or down-regulation with immediate or delayed rebound
        - The full power consumption is shifted
        - In total, it is possible to shift 2 * 'shiftable_hours' of power consumption
            -- (Multiply by 2 due to rebound)
        - The optimization is run for each day in the spot price data
        - It is also assumed that the BRP buys the energy resulting from this optimization

    This allows us to solve the problem using a greedy approach:
        - Sort the abslute value of differentiated spot prices in descending order
        - Choose the hour with the biggest price differential and shift the power consumption
        - Rebound in the following or preceeding hour(s) (depending if price differential is positive or negative)

    return:
        - Costs w/wo load shifting for all days

    Possible improvements/extensions:
    If *all* of the above constraints are relaxed, the problem becomes a very simple linear program.
        - Only constraint: sum of power must equal base power consumption
        - For example, a battery
    If *some* of the above constraints are relaxed, the problem *can* become a rather complicated mixed integer linear program.
        - For example, immediate rebound but with specific rebound patterns
    """

    # mask out hours that are not shiftable
    mask = np.isnan(base_power)
    assert mask.shape == spot_price.shape
    assert mask.shape == base_power.shape

    base_power[mask] = hourly_base_power

    base_cost = spot_price * base_power

    mem_power = base_power.copy()
    mem_cost = base_cost.copy()

    # adjust power to what is flexible
    _base_power = base_power * percent_flexible

    mem_savings = {}
    mem_consumption = {}

    for d in range(spot_price.shape[0]):

        daily_price = spot_price[d, :]

        actions = []
        values = []

        for i in range(24):
            for j in range(24):
                # only look at lower (or upper) triangle of matrix
                # only look at eligible hours for load shifting
                if j <= i or mask[d, i] or mask[d, j]:
                    continue

                if abs(i - j) > 1 and immediate_rebound:
                    continue

                # up-regulate in i and down-regulate in j using power in i
                up_down_cost = (
                    -daily_price[i] * _base_power[d, i]
                    + daily_price[j] * _base_power[d, i] * shifted_load_percentage
                )
                # down-regulate in i and up-regulate in j using power in j
                down_up_cost = (
                    daily_price[i] * _base_power[d, j] * shifted_load_percentage
                    - daily_price[j] * _base_power[d, j]
                )
                # TODO: use a setting instead. It ensures rebound happens after up-regulation
                down_up_cost = 0.0

                # hence, we either move i's power to j or j's power to i,
                # whichever is cheaper (and cheaper than doing nothing, i.e. 0):

                if up_down_cost < down_up_cost and up_down_cost < 0:
                    mem_savings[(d, i, j)] = (
                        # 0.0,
                        -daily_price[i] * _base_power[d, i],
                        daily_price[j] * _base_power[d, i] * shifted_load_percentage,
                    )
                    mem_consumption[(d, i, j)] = (
                        -_base_power[d, i],
                        _base_power[d, i] * shifted_load_percentage,
                    )
                    val = up_down_cost
                elif down_up_cost < up_down_cost and down_up_cost < 0:
                    mem_savings[(d, i, j)] = (
                        daily_price[i] * _base_power[d, j] * shifted_load_percentage,
                        -daily_price[j] * _base_power[d, j],
                        # 0.0
                    )
                    mem_consumption[(d, i, j)] = (
                        _base_power[d, j] * shifted_load_percentage,
                        -_base_power[d, j],
                    )
                    val = down_up_cost

                if (d, i, j) in mem_savings and (d, i, j) in mem_consumption:
                    # append action and its value
                    actions.append((i, j))
                    values.append(val)  # type:ignore

        # sort best actions by lowest value and discard overlapping keys
        unique_sorted_actions: List[Tuple[int, int]] = []
        ix = np.argsort(values)
        for i in ix:
            i, j = actions[i]
            overlapping_actions = [
                True if (i in a or j in a) else False for a in unique_sorted_actions
            ]
            if sum(overlapping_actions) == 0:
                unique_sorted_actions.append((i, j))

        if len(unique_sorted_actions) == 0:
            print(
                "Warning: No actions to take!",
                end="\r",
            )
            continue

        if len(unique_sorted_actions) < shiftable_hours:
            print(
                f"Warning: can't utilize all available hours to shift load {len(unique_sorted_actions)}/{d}",
                end="\r",
            )

        for i, j in unique_sorted_actions[:shiftable_hours]:
            v1, v2 = mem_savings[(d, i, j)]
            p1, p2 = mem_consumption[(d, i, j)]
            mem_cost[d, i] += v1
            mem_cost[d, j] += v2
            mem_power[d, i] += p1
            mem_power[d, j] += p2

    return OptimizationResult(base_cost, mem_cost, mem_power)


@timing()
def get_power_array(
    spot: pd.DataFrame,
    power: pd.DataFrame,
) -> np.ndarray:

    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    power.index = power.Hour

    power_dict = power.to_dict()
    if spot.shape[0] <= 24:
        # if spot price data is less-eq than a day, we only use power specified on Monday for all days
        for wd in weekdays[1:]:
            power_dict[wd] = power_dict["Mon"]

    # compute power values to spot so weekday matches
    def get_power(x: pd.Series) -> float:
        wd = x.weekday()
        _wd = weekdays[wd]
        h = x.hour + 1
        # Set power to 'nan' if user didn't specify power consumption for that weekday/hour.
        # This power will be identified in the optimization and will not be shifted, but instead
        # set to BASE_LOAD.
        p = (
            float(power_dict[_wd][h])
            if (power_dict.get(_wd) is not None and power_dict[_wd].get(h) is not None)
            else np.nan
        )
        return p

    return spot.HourUTC.apply(lambda x: get_power(x)).values.reshape(-1, 24)


@timing()
def prepare_and_run_optimization(
    spot: pd.DataFrame,
    power: pd.DataFrame,
    shiftable_hours: int,
    immediate_rebound_str: str,
    hourly_base_power: float,
    percent_flexible: float,
    shifted_load_percentage: float,
) -> Any:

    immediate_rebound = True if immediate_rebound_str == "Immediate" else False

    assert shiftable_hours is not None, "Shiftable hours must be specified"
    assert spot.shape[0] % 24 == 0, "Spot prices must be 24 hours long"
    assert percent_flexible >= 0 and percent_flexible <= 1

    spot_array = spot.SpotPriceDKK.values.reshape(-1, 24)
    power_array = get_power_array(spot, power)

    spot["power"] = power_array.reshape(-1)

    assert (
        power_array.shape == spot_array.shape
    ), "power_array.shape == spot_array.shape"

    print(f"Spot array shape: {spot_array.shape}")

    opt_result = run_optimization(
        spot_array,
        power_array,
        shiftable_hours,
        immediate_rebound,
        hourly_base_power,
        percent_flexible,
        shifted_load_percentage,
    )
    flexible_power_response = opt_result.mem_power.reshape(-1)
    power_array[np.isnan(power_array)] = hourly_base_power
    power_array = power_array.reshape(-1)

    if shifted_load_percentage == 1:
        assert np.isclose(
            sum(flexible_power_response),
            sum(power_array),
            1e-3,
        ), "There is a bug in the optimization. Please report it."
    else:
        assert sum(flexible_power_response) < sum(
            power_array
        ), "There is a bug in the optimization. Please report it."

    @timing()
    def create_result_plot() -> Any:
        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            subplot_titles=(
                "Spot price",
                "Cumulative cost w./wo. spot price optimization",
                "Power consumption",
            ),
        )
        fig.add_trace(
            go.Scatter(
                x=spot.HourUTC,
                y=spot.SpotPriceDKKCopy.values,
                mode="lines",
                name="Spot price",
                line_shape="hv",
                legendgroup="1",
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=spot.HourUTC,
                y=(spot.SpotPriceDKK.values - spot.SpotPriceDKKCopy.values),
                mode="lines",
                name="Tariff",
                line_shape="hv",
                legendgroup="1",
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=spot.HourUTC,
                y=(spot.SpotPriceDKK.values),
                mode="lines",
                name="Spot price + tariff",
                line_shape="hv",
                legendgroup="1",
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=spot.HourUTC,
                y=np.cumsum(opt_result.mem_cost.reshape(-1)),
                mode="lines",
                name="With load shifting",
                line_shape="hv",
                legendgroup="2",
            ),
            row=2,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=spot.HourUTC,
                y=np.cumsum(opt_result.base_cost.reshape(-1)),
                mode="lines",
                name="Without load shifting",
                line_shape="hv",
                legendgroup="2",
            ),
            row=2,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=spot.HourUTC,
                y=power_array,
                mode="lines",
                name="Without load shifting",
                line_shape="hv",
                legendgroup="3",
            ),
            row=3,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=spot.HourUTC,
                y=flexible_power_response,
                mode="lines",
                name="With load shifting",
                line_shape="hv",
                legendgroup="3",
            ),
            row=3,
            col=1,
        )
        # TODO: speed up below rendering of shapes for hours not allowed. It's way too slow.
        # ix = spot.power.isna()
        # masked_hours = (
        #     spot[ix].groupby((~ix).cumsum())["HourUTC"].agg(["first", "last"])
        # )
        # for index, row in masked_hours.iterrows():
        #     # print(row['first'], row['last'])
        #     fig.add_shape(
        #         type="rect",
        #         xref="x",
        #         yref="paper",
        #         x0=row["first"],
        #         y0=0,
        #         x1=row["last"],
        #         y1=spot.power.max(),
        #         line=dict(
        #             color="rgba(0,0,0,0)",
        #             width=3,
        #         ),
        #         fillcolor="rgba(255,0,0,0.2)",
        #         layer="below",
        #         row=3,
        #         col=1,
        #     )
        i_max = 24 if len(spot_array.reshape(-1)) > 24 else 23
        fig.update_layout(
            font=dict(
                family="Courier New, monospace",
                size=18,
                color="#7f7f7f",
            ),
            height=700,
            xaxis=dict(
                range=[
                    spot.HourUTC.iloc[0] - timedelta(minutes=60),
                    spot.HourUTC.iloc[23] + timedelta(minutes=120),
                ]
            ),
            xaxis3=dict(title="Time"),
            yaxis1=dict(
                range=[0, np.max(spot_array.reshape(-1)[:i_max]) + 150],
                title="DKK/MWh",
            ),
            yaxis2=dict(
                range=[0, np.cumsum(opt_result.base_cost.reshape(-1))[i_max] * 1.1],
                title="DKK",
            ),
            yaxis3=dict(title="MW", range=[0, flexible_power_response.max() * 1.1]),
            legend_tracegroupgap=150,
        )

        return fig

    fig = create_result_plot()

    return opt_result, fig
