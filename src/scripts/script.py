#%%
# Import necessary libraries
from typing import cast

import numpy as np
import pandas as pd

DEFAULT_POWER = 1.0  # mW

if True:
    from src.load_shifting.optimization import prepare_and_run_optimization
    from src.load_shifting.pages.Spot_Prices import read_spot_price_data


def read_power_data(hourly_base_power: float) -> pd.DataFrame:
    power = pd.DataFrame(
        np.ones((24, 7)) * hourly_base_power,
        index=list(range(1, 25)),
        columns=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    ).reset_index()
    power = power.rename(columns={"index": "Hour"})
    return power


hourly_base_power = 0.114

power_df = read_power_data(hourly_base_power)
spot_price_df = read_spot_price_data()

res = []
for scen in ["scenario1", "scenario2", "scenario3"]:
    if scen == "scenario3":
        _power_df = power_df.copy()
    elif scen == "scenario2":
        _power_df = power_df.query("Hour >= 8 & Hour <= 16").copy()
        _power_df = _power_df[["Hour", "Mon", "Tue", "Wed", "Thu", "Fri"]]
    elif scen == "scenario1":
        _power_df = power_df.query("Hour >= 7 & Hour <= 22").copy()
    else:
        raise ValueError("Invalid scenario")
    for area in ["DK1", "DK2"]:
        for year in [2021, 2022]:
            for immediate_rebound in ["Immediate", "Delayed"]:
                spot_area = spot_price_df.query("PriceArea == @area").copy()
                spot_area_year = spot_area.query("HourUTC.dt.year == @year").copy()
                for shiftable_hours in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]:
                    try:
                        opt_result, fig = prepare_and_run_optimization(
                            spot_area_year.copy(),
                            _power_df.copy(),
                            cast(int, shiftable_hours),
                            cast(str, immediate_rebound),
                            hourly_base_power,
                        )
                    except AssertionError:
                        continue

                    base_cost = sum(opt_result.base_cost.reshape(-1))
                    shifted_cost = sum(opt_result.mem_cost.reshape(-1))
                    savings = (base_cost - shifted_cost) / base_cost * 100

                    _res = {
                        "base_cost": base_cost,
                        "shifted_cost": shifted_cost,
                        "savings": savings,
                    }
                    param_set = {
                        "scenario": scen,
                        "immediate_rebound": immediate_rebound,
                        "shiftable_hours": shiftable_hours,
                        "area": area,
                        "year": year,
                    }
                    _res.update(param_set)
                    res.append(_res)


#%%
df = pd.DataFrame(res)
df[["base_cost", "shifted_cost"]] = df[["base_cost", "shifted_cost"]].round()

df.to_csv("experiment.csv", index=False)
