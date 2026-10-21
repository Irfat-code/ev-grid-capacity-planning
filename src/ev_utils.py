"""Reusable helpers for the EV capacity planning notebooks."""
import numpy as np
import pandas as pd

EARTH_RADIUS_KM = 6371.0


def parse_coords(s: pd.Series) -> pd.DataFrame:
    """Turn text tuples like '(64.02, -129.53)' into numeric lat/lon columns."""
    xy = s.str.strip("()").str.split(",", expand=True).astype(float)
    xy.columns = ["lat", "lon"]
    return xy


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km. Works on scalars or aligned arrays."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def to_snake(col: str) -> str:
    """'Electricity_Consumption (kWh)' -> 'electricity_consumption_kwh'."""
    out = col.lower().replace("°c", "c")
    for ch in "()":
        out = out.replace(ch, "")
    return "_".join(out.replace("-", " ").replace("_", " ").split())


def capacity_model(events: pd.DataFrame, substations: pd.DataFrame, charger_kw: dict,
                   base_load_util: float, coincidence: float, planning_limit: float,
                   growth: float = 1.0) -> pd.DataFrame:
    """Peak utilisation per substation for one set of assumptions.

    EV peak MW = sum of connected charger power (EVs x charger kW) x coincidence factor.
    Utilisation = existing (non-EV) base load share + EV peak x growth / capacity.
    """
    connected_kw = events["number_of_evs"] * events["charger_type"].map(charger_kw)
    ev_peak_mw = (connected_kw.groupby(events["substation_id"]).sum()
                  .reindex(substations["substation_id"], fill_value=0) * coincidence / 1000)
    out = substations.set_index("substation_id")[["capacity_mw"]].copy()
    out["ev_peak_mw"] = ev_peak_mw
    out["base_load_mw"] = base_load_util * out["capacity_mw"]
    out["peak_load_mw"] = out["base_load_mw"] + out["ev_peak_mw"] * growth
    out["utilisation"] = out["peak_load_mw"] / out["capacity_mw"]
    out["headroom_mw"] = planning_limit * out["capacity_mw"] - out["peak_load_mw"]
    # How many times today's EV load the substation can absorb before hitting the planning limit
    out["breaking_multiple"] = ((planning_limit - base_load_util) * out["capacity_mw"]
                                / out["ev_peak_mw"].replace(0, np.nan))
    return out
