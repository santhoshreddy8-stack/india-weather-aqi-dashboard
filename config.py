"""Central settings. Change cities or refresh timings here only."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "weather.db"

TIMEZONE = "Asia/Kolkata"
REQUEST_TIMEOUT = 10            # seconds per API call
COLLECT_EVERY_SECONDS = 300     # fetch new data at most every 5 minutes
RETRY_AFTER_ERROR_SECONDS = 60  # if a fetch failed, try again after 1 minute
UI_REFRESH_SECONDS = 60         # dashboard re-draws every minute
HISTORY_DAYS = 2                # days of history back-filled on first run

# city: (latitude, longitude)
CITIES = {
    "Delhi": (28.6139, 77.2090),
    "Mumbai": (19.0760, 72.8777),
    "Bengaluru": (12.9716, 77.5946),
    "Chennai": (13.0827, 80.2707),
    "Kolkata": (22.5726, 88.3639),
    "Hyderabad": (17.3850, 78.4867),
    "Visakhapatnam": (17.6868, 83.2185),
    "Ahmedabad": (23.0225, 72.5714),
}

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"