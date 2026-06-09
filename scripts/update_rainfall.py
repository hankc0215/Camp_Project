import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from pykrige.ok import OrdinaryKriging
except ImportError:
    OrdinaryKriging = None


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CSV_PATH = DATA_DIR / "all_taiwan_camping_risk_demo.csv"
JSON_OUT = DATA_DIR / "real_rainfall.json"
JS_OUT = DATA_DIR / "real_rainfall.js"
CWA_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0002-001"


def load_env_files():
    env_paths = [
        ROOT / ".env",
        ROOT.parent / ".env",
        ROOT.parent.parent / ".env",
        Path.cwd() / ".env",
    ]
    for env_path in env_paths:
        if not env_path.exists():
            continue
        if load_dotenv:
            load_dotenv(env_path)
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def clean_rain_value(value):
    try:
        rain = float(value)
        return rain if rain >= 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def read_rainfall_element(station, key):
    value = station.get("RainfallElement", {}).get(key, {})
    if isinstance(value, dict):
        return clean_rain_value(value.get("Precipitation", 0))
    return clean_rain_value(value)


def fetch_cwa_stations(api_key):
    query = urllib.parse.urlencode({"Authorization": api_key, "format": "JSON"})
    with urllib.request.urlopen(f"{CWA_URL}?{query}", timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    stations = data.get("records", {}).get("Station", [])
    valid = []

    for station in stations:
        lat = None
        lon = None
        for coord in station.get("GeoInfo", {}).get("Coordinates", []):
            if coord.get("CoordinateName") == "WGS84":
                lat = coord.get("StationLatitude")
                lon = coord.get("StationLongitude")
                break
        if lat is None or lon is None:
            continue

        rain_1h = read_rainfall_element(station, "Past1hr")
        rain_3h = read_rainfall_element(station, "Past3hr")
        rain_24h = read_rainfall_element(station, "Past24hr")

        valid.append(
            {
                "id": station.get("StationId", ""),
                "name": station.get("StationName", ""),
                "county": station.get("GeoInfo", {}).get("CountyName", ""),
                "town": station.get("GeoInfo", {}).get("TownName", ""),
                "obs_time": station.get("ObsTime", {}).get("DateTime", ""),
                "lon": float(lon),
                "lat": float(lat),
                "rain_1h": rain_1h,
                "rain_3h": rain_3h,
                "rain_24h": rain_24h,
            }
        )

    stations_df = pd.DataFrame(valid)
    if stations_df.empty:
        raise RuntimeError("CWA response did not include usable WGS84 rainfall stations.")
    return stations_df


def haversine_km(lon1, lat1, lon2, lat2):
    radius = 6371.0
    lon1 = np.radians(lon1)
    lat1 = np.radians(lat1)
    lon2 = np.radians(lon2)
    lat2 = np.radians(lat2)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return radius * 2 * np.arcsin(np.sqrt(a))


def nearest_station(camp_lon, camp_lat, stations_df):
    distances = haversine_km(
        camp_lon,
        camp_lat,
        stations_df["lon"].to_numpy(),
        stations_df["lat"].to_numpy(),
    )
    idx = int(np.argmin(distances))
    row = stations_df.iloc[idx]
    return row, float(distances[idx])


def idw_interpolate(stations_df, camps_lon, camps_lat, value_col, power=2):
    station_lon = stations_df["lon"].to_numpy()
    station_lat = stations_df["lat"].to_numpy()
    station_rain = stations_df[value_col].to_numpy()
    values = []

    for lon, lat in zip(camps_lon, camps_lat):
        distances = haversine_km(lon, lat, station_lon, station_lat)
        if np.any(distances < 0.001):
            values.append(float(station_rain[np.argmin(distances)]))
            continue
        weights = 1 / np.power(np.maximum(distances, 0.001), power)
        values.append(float(np.sum(weights * station_rain) / np.sum(weights)))

    return np.array(values)


def interpolate_rain(stations_df, camps_lon, camps_lat, value_col):
    max_rain = float(stations_df[value_col].max())
    if max_rain == 0:
        return np.zeros(len(camps_lon)), "zero_rain"

    if OrdinaryKriging is None:
        return idw_interpolate(stations_df, camps_lon, camps_lat, value_col), "idw_fallback"

    ok = OrdinaryKriging(
        x=stations_df["lon"].to_numpy(),
        y=stations_df["lat"].to_numpy(),
        z=stations_df[value_col].to_numpy(),
        variogram_model="spherical",
        enable_plotting=False,
    )
    z_interp, _ = ok.execute("points", camps_lon, camps_lat)
    return np.asarray(np.clip(z_interp.data, a_min=0, a_max=None), dtype=float), "ordinary_kriging_spherical"


def build_rainfall(write_files=True):
    load_env_files()
    api_key = os.getenv("CWA_API_KEY") or os.getenv("CWA_AUTHORIZATION_KEY") or os.getenv("CWB_API_KEY")
    if not api_key:
        raise RuntimeError("Missing CWA_API_KEY. Copy .env.example to .env and fill in your CWA API key.")

    stations_df = fetch_cwa_stations(api_key)
    camps_df = pd.read_csv(CSV_PATH).dropna(subset=["lon", "lat"]).copy()
    camps_lon = camps_df["lon"].astype(float).to_numpy()
    camps_lat = camps_df["lat"].astype(float).to_numpy()
    rain_1h_values, method_1h = interpolate_rain(stations_df, camps_lon, camps_lat, "rain_1h")
    rain_3h_values, method_3h = interpolate_rain(stations_df, camps_lon, camps_lat, "rain_3h")
    rain_24h_values, method_24h = interpolate_rain(stations_df, camps_lon, camps_lat, "rain_24h")
    method = method_24h
    camps_df["rain_1h_mm_real"] = np.round(rain_1h_values, 2)
    camps_df["rain_3h_mm_real"] = np.round(rain_3h_values, 2)
    camps_df["rain_24h_mm_real"] = np.round(rain_24h_values, 2)

    by_priority_rank = {}
    for idx, row in camps_df.iterrows():
        station, station_distance_km = nearest_station(float(row["lon"]), float(row["lat"]), stations_df)
        by_priority_rank[str(row["priority_rank"])] = {
            "rain_1h_mm_real": float(row["rain_1h_mm_real"]),
            "rain_3h_mm_real": float(row["rain_3h_mm_real"]),
            "rain_24h_mm_real": float(row["rain_24h_mm_real"]),
            "rain_interpolation_method": method,
            "rain_station_id": station["id"],
            "rain_station_name": station["name"],
            "rain_station_county": station["county"],
            "rain_station_town": station["town"],
            "rain_station_distance_km": round(station_distance_km, 2),
            "rain_observed_at": station["obs_time"],
        }

    output = {
        "source": "CWA O-A0002-001",
        "generated_at": pd.Timestamp.now(tz="Asia/Taipei").isoformat(),
        "interpolation_method": method,
        "interpolation_methods": {
            "rain_1h_mm_real": method_1h,
            "rain_3h_mm_real": method_3h,
            "rain_24h_mm_real": method_24h,
        },
        "station_count": int(len(stations_df)),
        "station_max_1h_mm": float(stations_df["rain_1h"].max()),
        "station_max_3h_mm": float(stations_df["rain_3h"].max()),
        "station_max_24h_mm": float(stations_df["rain_24h"].max()),
        "campsite_count": int(len(by_priority_rank)),
        "by_priority_rank": by_priority_rank,
    }

    if write_files:
        JSON_OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        JS_OUT.write_text(
            "window.REAL_RAINFALL = " + json.dumps(output, ensure_ascii=False, indent=2) + ";\n",
            encoding="utf-8",
        )
    return output


def main():
    output = build_rainfall(write_files=True)
    print(f"Wrote {JSON_OUT}")
    print(f"Wrote {JS_OUT}")
    print(
        f"Matched {output['campsite_count']} campsites using {output['station_count']} CWA stations "
        f"with {output['interpolation_method']}."
    )


if __name__ == "__main__":
    main()
