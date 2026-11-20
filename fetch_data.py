"""Data collector: pulls live data from Open-Meteo and stores it in SQLite.

Run standalone:   python fetch_data.py          (loops forever)
                  python fetch_data.py --once   (single run)
The Streamlit app also calls collect_if_stale() automatically.
"""
import argparse
import logging
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config
import db

log = logging.getLogger("collector")

WEATHER_VARS = "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,wind_speed_10m"
AIR_VARS = "us_aqi,pm2_5,pm10"
AIR_COLS = ["us_aqi", "pm2_5", "pm10"]
RENAME = {
    "time": "observed_at",
    "temperature_2m": "temperature",
    "apparent_temperature": "apparent_temp",
    "relative_humidity_2m": "humidity",
    "wind_speed_10m": "wind_speed",
}

_session = requests.Session()
_session.mount(
    "https://",
    HTTPAdapter(max_retries=Retry(total=2, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504))),
)
_lock = threading.Lock()


def _get(url, params):
    resp = _session.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def fetch_current(city, lat, lon):
    """Latest weather + air quality for one city -> one row (dict)."""
    base = {"latitude": lat, "longitude": lon, "timezone": config.TIMEZONE}
    weather = _get(config.WEATHER_URL, {**base, "current": WEATHER_VARS})["current"]
    try:
        air = _get(config.AIR_URL, {**base, "current": AIR_VARS})["current"]
    except requests.RequestException as exc:  # weather alone is still useful
        log.warning("Air quality unavailable for %s: %s", city, exc)
        air = {}
    row = {RENAME.get(k, k): v for k, v in weather.items()}
    for col in AIR_COLS:
        row[col] = air.get(col)
    row["city"] = city
    return row


def fetch_history(city, lat, lon, days=config.HISTORY_DAYS):
    """Hourly history up to 'now' so charts are not empty on the first run."""
    base = {
        "latitude": lat, "longitude": lon, "timezone": config.TIMEZONE,
        "past_days": days, "forecast_days": 1,
    }
    w = pd.DataFrame(_get(config.WEATHER_URL, {**base, "hourly": WEATHER_VARS})["hourly"])
    try:
        a = pd.DataFrame(_get(config.AIR_URL, {**base, "hourly": AIR_VARS})["hourly"])
    except requests.RequestException as exc:
        log.warning("Air history unavailable for %s: %s", city, exc)
        a = pd.DataFrame({"time": w["time"]})
    df = w.merge(a, on="time", how="left")
    for col in AIR_COLS:
        if col not in df.columns:
            df[col] = None
    now = datetime.now(ZoneInfo(config.TIMEZONE)).strftime("%Y-%m-%dT%H:%M")
    df = df[df["time"] <= now].rename(columns=RENAME)  # drop future hours
    df["city"] = city
    df = df.astype(object).where(df.notna(), None)      # NaN -> NULL
    return df.to_dict("records")


def collect_once():
    """Fetch every city once. Returns the number of successful cities."""
    db.init_db()
    ok = 0
    for city, (lat, lon) in config.CITIES.items():
        try:
            if db.count_readings(city) == 0:
                db.insert_readings(fetch_history(city, lat, lon))
            db.insert_readings([fetch_current(city, lat, lon)])
            db.log_fetch(city, "ok")
            ok += 1
        except Exception as exc:  # keep going if one city fails
            log.error("Fetch failed for %s: %s", city, exc)
            db.log_fetch(city, "error", str(exc)[:300])
    return ok


def collect_if_stale(force=False):
    """Collect only when data is old enough. Safe to call from many sessions."""
    if not _lock.acquire(blocking=False):
        return False  # another thread is already collecting
    try:
        db.init_db()
        if not force:
            now = datetime.now(timezone.utc)
            last_ok = db.last_fetch("ok")
            last_any = db.last_fetch()
            if last_ok and (now - last_ok).total_seconds() < config.COLLECT_EVERY_SECONDS:
                return False
            if last_any and (now - last_any).total_seconds() < config.RETRY_AFTER_ERROR_SECONDS:
                return False
        collect_once()
        return True
    finally:
        _lock.release()


GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"


def search_india_locations(query, count=8):
    """Search any state, city, town, or village in India via Open-Meteo Geocoding."""
    if not query or len(query.strip()) < 2:
        return []
    try:
        data = _get(
            GEOCODE_URL,
            {
                "name": query.strip(),
                "count": count,
                "language": "en",
                "format": "json",
                "countryCode": "IN",
            },
        )
        results = []
        for item in data.get("results", []):
            parts = [item.get("name", "")]
            if item.get("admin2") and item.get("admin2") != item.get("name"):
                parts.append(item["admin2"])
            if item.get("admin1"):
                parts.append(item["admin1"])
            results.append(
                {
                    "label": ", ".join(parts),
                    "name": item.get("name", ""),
                    "state": item.get("admin1", "India"),
                    "lat": item["latitude"],
                    "lon": item["longitude"],
                }
            )
        return results
    except requests.RequestException as exc:
        log.warning("Geocoding search failed: %s", exc)
        return []



def main():
    parser = argparse.ArgumentParser(description="Collect live weather and air quality data.")
    parser.add_argument("--once", action="store_true", help="run a single collection and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        while True:
            ok = collect_once()
            log.info("Collected %d/%d cities", ok, len(config.CITIES))
            if args.once:
                break
            time.sleep(config.COLLECT_EVERY_SECONDS)
    except KeyboardInterrupt:
        log.info("Stopped.")


if __name__ == "__main__":
    main()