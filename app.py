"""Streamlit dashboard. Run with:  streamlit run app.py"""
import pandas as pd
import plotly.express as px
import streamlit as st
import sqlite3
from sqlalchemy import create_engine

import analysis
import db
import fetch_data
from config import CITIES, COLLECT_EVERY_SECONDS, UI_REFRESH_SECONDS

st.set_page_config(page_title="India Live Weather & Air Quality", page_icon="🌦️", layout="wide")
db.init_db()

METRICS = {
    "Temperature (°C)": "temperature",
    "Feels like (°C)": "apparent_temp",
    "Humidity (%)": "humidity",
    "Wind speed (km/h)": "wind_speed",
    "Precipitation (mm)": "precipitation",
    "US AQI": "us_aqi",
    "PM2.5 (µg/m³)": "pm2_5",
    "PM10 (µg/m³)": "pm10",
}

st.title("🌦️ India Live Weather & Air Quality Dashboard")
st.caption("Pipeline: Open-Meteo API → Python collector → SQLite → Streamlit (auto-refreshing)")

with st.sidebar:
    st.header("Filters")
    selected = st.multiselect("Cities", list(CITIES), default=list(CITIES))
    hours = st.select_slider("Time window (hours)", options=[6, 12, 24, 48], value=24)
    if st.button("🔄 Fetch latest data now"):
        with st.spinner("Fetching live data..."):
            fetch_data.collect_if_stale(force=True)
    st.caption(
        f"New data is collected every {COLLECT_EVERY_SECONDS // 60} min. "
        f"The page redraws every {UI_REFRESH_SECONDS} s."
    )

if not selected:
    st.warning("Select at least one city in the sidebar.")
    st.stop()


@st.fragment(run_every=UI_REFRESH_SECONDS)
def live_dashboard(cities, window_hours):
    fetch_data.collect_if_stale()  # no-op unless data is older than 5 minutes

    df = db.read_readings(window_hours)
    df = df[df["city"].isin(cities)]
    if df.empty:
        st.info("No data yet. Check your internet connection, then click 'Fetch latest data now'.")
        return

    snap = analysis.latest_snapshot(df)
    snap["lat"] = snap["city"].map(lambda c: CITIES[c][0])
    snap["lon"] = snap["city"].map(lambda c: CITIES[c][1])

    # ---- KPI row
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Avg temperature", f"{snap['temperature'].mean():.1f} °C")
    k2.metric("Avg humidity", f"{snap['humidity'].mean():.0f} %")
    aqi_mean = snap["us_aqi"].mean()
    k3.metric("Avg US AQI", "n/a" if pd.isna(aqi_mean) else f"{aqi_mean:.0f}")
    k4.metric("Latest reading (IST)", snap["observed_at"].max().strftime("%d %b, %H:%M"))

    tab1, tab2, tab3 = st.tabs(["📍 Overview", "📈 Trends", "🛠️ Data & pipeline"])

    # ---- Overview
    with tab1:
        left, right = st.columns([3, 2])
        with left:
            fig = px.scatter_map(
                snap, lat="lat", lon="lon", color="aqi_category",
                color_discrete_map=analysis.AQI_COLORS, hover_name="city",
                hover_data={"temperature": ":.1f", "humidity": ":.0f", "us_aqi": ":.0f",
                            "lat": False, "lon": False, "aqi_category": False},
                zoom=3.4, center={"lat": 22.0, "lon": 80.0}, height=470,
                map_style="open-street-map",
            )
            fig.update_traces(marker={"size": 16})
            fig.update_layout(margin={"l": 0, "r": 0, "t": 0, "b": 0}, legend_title_text="AQI level")
            st.plotly_chart(fig, key="map_chart")
        with right:
            bar = px.bar(
                snap.sort_values("us_aqi"), x="us_aqi", y="city", orientation="h",
                color="aqi_category", color_discrete_map=analysis.AQI_COLORS,
                labels={"us_aqi": "US AQI", "city": ""}, height=470,
            )
            bar.update_layout(showlegend=False, margin={"l": 0, "r": 0, "t": 30, "b": 0}, title="Air quality by city")
            st.plotly_chart(bar, key="aqi_bar")

        st.subheader("Key insights")
        for line in analysis.build_insights(snap, df):
            st.markdown(f"- {line}")

        st.subheader("Latest snapshot")
        table = snap[["city", "temperature", "apparent_temp", "humidity", "wind_speed",
                      "precipitation", "us_aqi", "aqi_category", "pm2_5", "pm10"]].copy()
        table.columns = ["City", "Temp °C", "Feels like °C", "Humidity %", "Wind km/h",
                         "Rain mm", "US AQI", "AQI level", "PM2.5", "PM10"]
        st.dataframe(table.round(1), hide_index=True)

    # ---- Trends
    with tab2:
        label = st.selectbox("Metric", list(METRICS), key="trend_metric")
        col = METRICS[label]
        line = px.line(df, x="observed_at", y=col, color="city",
                       labels={"observed_at": "Time (IST)", col: label, "city": "City"}, height=420)
        line.update_layout(margin={"l": 0, "r": 0, "t": 10, "b": 0}, hovermode="x unified")
        st.plotly_chart(line, key="trend_line")

        heat = (
            df.assign(hour=df["observed_at"].dt.floor("h"))
            .pivot_table(index="city", columns="hour", values=col, aggfunc="mean")
        )
        if not heat.empty:
            hm = px.imshow(heat, aspect="auto", color_continuous_scale="RdYlGn_r",
                           labels={"x": "Hour", "y": "", "color": label}, height=360)
            hm.update_layout(margin={"l": 0, "r": 0, "t": 30, "b": 0}, title=f"{label}: city x hour heatmap")
            st.plotly_chart(hm, key="trend_heatmap")

    # ---- Pipeline
    with tab3:
        log = db.read_log(50)
        p1, p2, p3 = st.columns(3)
        p1.metric("Rows stored", f"{db.count_readings():,}")
        success = (log["status"] == "ok").mean() * 100 if not log.empty else 0
        p2.metric("Fetch success rate (last 50)", f"{success:.0f} %")
        p3.metric("Cities tracked", len(CITIES))
        st.subheader("Recent fetch log")
        st.dataframe(log.head(15), hide_index=True)
        st.download_button(
            "⬇️ Download data as CSV (use it in Power BI / Excel)",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="weather_air_quality.csv",
            mime="text/csv",
            key="csv_download",
        )

    st.caption("Weather data: Open-Meteo.com (CC BY 4.0). Air quality: CAMS ENSEMBLE / Copernicus via Open-Meteo.")


live_dashboard(selected, hours)