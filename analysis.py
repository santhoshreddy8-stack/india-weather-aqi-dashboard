"""Pure data logic (no UI): AQI categories, latest snapshot, auto-insights."""
import pandas as pd

AQI_BANDS = [
    (50, "Good", "#2e9e5b"),
    (100, "Moderate", "#e6b800"),
    (150, "Unhealthy for sensitive groups", "#f08a24"),
    (200, "Unhealthy", "#d63b3b"),
    (300, "Very unhealthy", "#8e44ad"),
    (float("inf"), "Hazardous", "#6b1d1d"),
]
AQI_COLORS = {label: color for _, label, color in AQI_BANDS}
AQI_COLORS["No data"] = "#9aa0a6"


def aqi_category(value):
    if value is None or pd.isna(value):
        return "No data"
    for upper, label, _ in AQI_BANDS:
        if value <= upper:
            return label
    return "Hazardous"


def latest_snapshot(df):
    """One row per city with the most recent non-null value of each column."""
    if df.empty:
        return df.copy()
    cols = [c for c in df.columns if c != "city"]
    snap = df.sort_values("observed_at").groupby("city")[cols].last().reset_index()
    snap["aqi_category"] = snap["us_aqi"].apply(aqi_category)
    return snap


def _delta(series):
    s = series.dropna()
    return s.iloc[-1] - s.iloc[0] if len(s) > 1 else float("nan")


def build_insights(snap, df):
    """Plain-English findings generated from the data."""
    out = []
    if snap.empty:
        return out

    t = snap.dropna(subset=["temperature"])
    if not t.empty:
        hot = t.loc[t["temperature"].idxmax()]
        cold = t.loc[t["temperature"].idxmin()]
        out.append(
            f"Hottest now: **{hot['city']}** at {hot['temperature']:.1f} °C "
            f"(feels like {hot['apparent_temp']:.1f} °C). Coolest: **{cold['city']}** at "
            f"{cold['temperature']:.1f} °C, a {hot['temperature'] - cold['temperature']:.1f} °C spread."
        )

    a = snap.dropna(subset=["us_aqi"])
    if not a.empty:
        worst = a.loc[a["us_aqi"].idxmax()]
        best = a.loc[a["us_aqi"].idxmin()]
        out.append(
            f"Worst air: **{worst['city']}** (US AQI {worst['us_aqi']:.0f}, {worst['aqi_category']}). "
            f"Best air: **{best['city']}** (US AQI {best['us_aqi']:.0f})."
        )
        bad = int((a["us_aqi"] > 100).sum())
        out.append(f"{bad} of {len(a)} cities are above AQI 100 (unhealthy for sensitive groups or worse).")

    ordered = df.sort_values("observed_at")
    change = ordered.groupby("city")["temperature"].agg(_delta).dropna()
    if not change.empty:
        city = change.abs().idxmax()
        word = "risen" if change[city] > 0 else "dropped"
        out.append(f"Biggest temperature swing in this window: **{city}** has {word} by {abs(change[city]):.1f} °C.")

    pair = df[["temperature", "us_aqi"]].dropna()
    if len(pair) >= 20:
        corr = pair["temperature"].corr(pair["us_aqi"])
        if pd.notna(corr):
            out.append(f"Temperature vs AQI correlation across all readings: {corr:+.2f} (correlation, not causation).")
    return out