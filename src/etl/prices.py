#%%
import numpy as np
import pandas as pd

# download from # https://www.energidataservice.dk/tso-electricity/Elspotprices
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
spot = spot.query("PriceArea == 'DK1' | PriceArea == 'DK2'")
spot.reset_index(drop=True, inplace=True)

print(spot.shape)

# download from https://www.energidataservice.dk/tso-electricity/DatahubPricelist
file = "src/data/DataHubPricelist.csv"
df = pd.read_csv(file, sep=";", decimal=",", parse_dates=["ValidFrom", "ValidTo"])

# DSO_DK1 = ["N1 A/S - 131", "N1 A/S - 344"]
RADIUS = {
    "Radius Elnet A/S": [
        "DT_C_01",
        # "DT_C_02",
        # "DT_C_03",
        "DT_B_01",
        "DT_B_02",
        # "DT_A_01",
        "DT_A_02",
        "DT_A_03",
    ],
    "area": "DK2",
}

# print(df.ChargeOwner.unique())
# print(len(df.ChargeTypeCode.unique()))
# print(df.ChargeTypeCode.unique())
# print(len(df.Note.unique()))
# print(df.Note.unique())
# print(df.ChargeTypeCode.value_counts().iloc[:50])


owner = "Radius Elnet A/S"
area = RADIUS["area"]
type = "DT_C_01"
rad = df.query(f"ChargeOwner == '{owner}' & ChargeTypeCode == '{type}'")
rad = df.query(
    f"ChargeOwner == '{owner}' & ChargeTypeCode == @RADIUS['Radius Elnet A/S']"
)


def get_tariff(x: pd.Series, owner: str, area: str, type: str):
    d = x.date().strftime("%Y-%m-%d")
    tmp = rad.query(f"ValidFrom <= '{d}' & ValidTo > '{d}'")
    col = f"Price{x.hour+1}"
    # compute average of "col" per ChargeTypeCode in tmp:
    tmp = tmp.groupby("ChargeTypeCode")[col].mean() * 1000
    return tmp


r = spot.query(f"PriceArea == '{area}'").HourUTC.apply(
    lambda x: get_tariff(x, owner, area, type)
)
cols = [f"{owner} {e}" for e in r.columns.tolist()]
spot.loc[r.index, cols] = r.values

# From https://n1.dk/priser-og-vilkaar
# tuple of (type, hour from, hour to, month from, month to)
# TODO: not correct until weekdays are taken into account
N1 = {
    ("C-time", 0, 23, 3, 8): 43.22 / 100 * 1000,  # lavlast
    ("C-time", 0, 23, 0, 2): 43.22 / 100 * 1000,  # lavlast
    ("C-time", 0, 23, 9, 12): 43.22 / 100 * 1000,  # lavlast
    ("C-time", 17, 19, 0, 2): 105.62 / 100 * 1000,  # spidslast
    ("C-time", 17, 19, 9, 12): 105.62 / 100 * 1000,  # spidslast
    ("B-lav", 23, 23, 3, 8): 16.57 / 100 * 1000,  # lavlast
    ("B-lav", 0, 6, 3, 8): 16.57 / 100 * 1000,  # lavlast
    ("B-lav", 0, 5, 0, 2): 16.57 / 100 * 1000,  # lavlast
    ("B-lav", 0, 5, 9, 12): 16.57 / 100 * 1000,  # lavlast
    ("B-lav", 7, 22, 3, 8): 30.89 / 100 * 1000,  # højlast
    ("B-lav", 6, 6, 0, 2): 30.89 / 100 * 1000,  # højlast
    ("B-lav", 6, 6, 9, 12): 30.89 / 100 * 1000,  # højlast
    ("B-lav", 20, 23, 0, 2): 30.89 / 100 * 1000,  # højlast
    ("B-lav", 20, 23, 9, 12): 30.89 / 100 * 1000,  # højlast
    ("B-lav", 7, 19, 0, 2): 45.44 / 100 * 1000,  # spidslast
    ("B-lav", 7, 19, 9, 12): 45.44 / 100 * 1000,  # spidslast
    # B 20 GWh has same periods as B-lav
    ("B 20 GWh", 23, 23, 3, 8): 7.72 / 100 * 1000,  # lavlast
    ("B 20 GWh", 0, 6, 3, 8): 7.72 / 100 * 1000,  # lavlast
    ("B 20 GWh", 0, 5, 0, 2): 7.72 / 100 * 1000,  # lavlast
    ("B 20 GWh", 0, 5, 9, 12): 7.72 / 100 * 1000,  # lavlast
    ("B 20 GWh", 7, 22, 3, 8): 13.87 / 100 * 1000,  # højlast
    ("B 20 GWh", 6, 6, 0, 2): 13.87 / 100 * 1000,  # højlast
    ("B 20 GWh", 6, 6, 9, 12): 13.87 / 100 * 1000,  # højlast
    ("B 20 GWh", 20, 23, 0, 2): 13.87 / 100 * 1000,  # højlast
    ("B 20 GWh", 20, 23, 9, 12): 13.87 / 100 * 1000,  # højlast
    ("B 20 GWh", 7, 19, 0, 2): 19.96 / 100 * 1000,  # spidslast
    ("B 20 GWh", 7, 19, 9, 12): 19.96 / 100 * 1000,  # spidslast
    # B-Høj has same periods as B-lav
    ("B-Høj", 23, 23, 3, 8): 12.27 / 100 * 1000,  # lavlast
    ("B-Høj", 0, 6, 3, 8): 12.27 / 100 * 1000,  # lavlast
    ("B-Høj", 0, 5, 0, 2): 12.27 / 100 * 1000,  # lavlast
    ("B-Høj", 0, 5, 9, 12): 12.27 / 100 * 1000,  # lavlast
    ("B-Høj", 7, 22, 3, 8): 23.63 / 100 * 1000,  # højlast
    ("B-Høj", 6, 6, 0, 2): 23.63 / 100 * 1000,  # højlast
    ("B-Høj", 6, 6, 9, 12): 23.63 / 100 * 1000,  # højlast
    ("B-Høj", 20, 23, 0, 2): 23.63 / 100 * 1000,  # højlast
    ("B-Høj", 20, 23, 9, 12): 23.63 / 100 * 1000,  # højlast
    ("B-Høj", 7, 19, 0, 2): 35.49 / 100 * 1000,  # spidslast
    ("B-Høj", 7, 19, 9, 12): 35.49 / 100 * 1000,  # spidslast
    # A-lav has same periods as B-lav
    ("A-lav", 23, 23, 3, 8): 3.81 / 100 * 1000,  # lavlast
    ("A-lav", 0, 6, 3, 8): 3.81 / 100 * 1000,  # lavlast
    ("A-lav", 0, 5, 0, 2): 3.81 / 100 * 1000,  # lavlast
    ("A-lav", 0, 5, 9, 12): 3.81 / 100 * 1000,  # lavlast
    ("A-lav", 7, 22, 3, 8): 6.96 / 100 * 1000,  # højlast
    ("A-lav", 6, 6, 0, 2): 6.96 / 100 * 1000,  # højlast
    ("A-lav", 6, 6, 9, 12): 6.96 / 100 * 1000,  # højlast
    ("A-lav", 20, 23, 0, 2): 6.96 / 100 * 1000,  # højlast
    ("A-lav", 20, 23, 9, 12): 6.96 / 100 * 1000,  # højlast
    ("A-lav", 7, 19, 0, 2): 10.12 / 100 * 1000,  # spidslast
    ("A-lav", 7, 19, 9, 12): 10.12 / 100 * 1000,  # spidslast
    # A-lav 200 GWh has same periods as B-lav
    ("A-lav 200 GWh", 23, 23, 3, 8): 3.45 / 100 * 1000,  # lavlast
    ("A-lav 200 GWh", 0, 6, 3, 8): 3.45 / 100 * 1000,  # lavlast
    ("A-lav 200 GWh", 0, 5, 0, 2): 3.45 / 100 * 1000,  # lavlast
    ("A-lav 200 GWh", 0, 5, 9, 12): 3.45 / 100 * 1000,  # lavlast
    ("A-lav 200 GWh", 7, 22, 3, 8): 5.57 / 100 * 1000,  # højlast
    ("A-lav 200 GWh", 6, 6, 0, 2): 5.57 / 100 * 1000,  # højlast
    ("A-lav 200 GWh", 6, 6, 9, 12): 5.57 / 100 * 1000,  # højlast
    ("A-lav 200 GWh", 20, 23, 0, 2): 5.57 / 100 * 1000,  # højlast
    ("A-lav 200 GWh", 20, 23, 9, 12): 5.57 / 100 * 1000,  # højlast
    ("A-lav 200 GWh", 7, 19, 0, 2): 7.78 / 100 * 1000,  # spidslast
    ("A-lav 200 GWh", 7, 19, 9, 12): 7.78 / 100 * 1000,  # spidslast
    # A-høj has same periods as B-lav
    ("A-høj", 23, 23, 3, 8): 2.3 / 100 * 1000,  # lavlast
    ("A-høj", 0, 6, 3, 8): 2.3 / 100 * 1000,  # lavlast
    ("A-høj", 0, 5, 0, 2): 2.3 / 100 * 1000,  # lavlast
    ("A-høj", 0, 5, 9, 12): 2.3 / 100 * 1000,  # lavlast
    ("A-høj", 7, 22, 3, 8): 4.42 / 100 * 1000,  # højlast
    ("A-høj", 6, 6, 0, 2): 4.42 / 100 * 1000,  # højlast
    ("A-høj", 6, 6, 9, 12): 4.42 / 100 * 1000,  # højlast
    ("A-høj", 20, 23, 0, 2): 4.42 / 100 * 1000,  # højlast
    ("A-høj", 20, 23, 9, 12): 4.42 / 100 * 1000,  # højlast
    ("A-høj", 7, 19, 0, 2): 6.63 / 100 * 1000,  # spidslast
    ("A-høj", 7, 19, 9, 12): 6.63 / 100 * 1000,  # spidslast
}

owner = "N1"
area = "DK1"
types = np.unique([k[0] for k, _ in N1.items()]).tolist()


def get_n1_tariff(x: pd.Series, type: str):
    m = x.month
    h = x.hour

    for k, v in N1.items():
        if k[0] == type and k[1] <= h <= k[2] and k[3] <= m <= k[4]:
            return v

    raise Exception(f"Could not find tariff for {type} {m} {h}")


for type in types:
    r = spot.query(f"PriceArea == '{area}'").HourUTC.apply(
        lambda x: get_n1_tariff(x, type)
    )
    col = f"{owner} {type}"
    spot.loc[r.index, col] = r.values

spot.to_csv("src/data/spot_with_tariffs.csv", index=False)
