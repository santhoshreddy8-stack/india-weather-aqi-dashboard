"""Streamlit dashboard with India-wide search and high-gradient UI."""
import pandas as pd
import plotly.express as px
import streamlit as st

import analysis
import db
import fetch_data
from config import CITIES, COLLECT_EVERY_SECONDS, UI_REFRESH_SECONDS
import folium
from streamlit_folium import st_folium
from streamlit_searchbox import st_searchbox

st.set_page_config(
    page_title="India Live Weather & Air Quality",
    page_icon="🌦️",
    layout="wide",
)
db.init_db()

# ---- High-Gradient Custom CSS ----
st.markdown(
    """
    <style>
    /* Main app background */
    .stApp {
        background: linear-gradient(135deg, #0f0c29 0%, #1a1a40 40%, #24243e 75%, #16213e 100%);
        color: #f8fafc;
    }

    /* Sidebar gradient */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #120e36 0%, #1e1b4b 50%, #0f172a 100%);
        border-right: 1px solid rgba(139, 92, 246, 0.3);
    }

    /* Gradient Hero Title */
    .hero-title {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8, #818cf8, #e879f9, #fb7185);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .hero-sub {
        color: #cbd5e1;
        font-size: 0.95rem;
        margin-bottom: 1.2rem;
    }

    /* Glassmorphic KPI metric cards */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(56, 189, 248, 0.14), rgba(168, 85, 247, 0.16));
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-radius: 16px;
        padding: 16px 20px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
        backdrop-filter: blur(10px);
    }
    [data-testid="stMetricLabel"] {
        color: #cbd5e1 !important;
        font-weight: 600;
    }
    [data-testid="stMetricValue"] {
        background: linear-gradient(90deg, #38bdf8, #f472b6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }

    /* Gradient Spotlight Box for Searched Location */
    .search-card {
        background: linear-gradient(135deg, rgba(14, 165, 233, 0.18), rgba(139, 92, 246, 0.22), rgba(236, 72, 153, 0.15));
        border: 1px solid rgba(192, 132, 252, 0.45);
        border-radius: 18px;
        padding: 20px 24px;
        margin-bottom: 20px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
    }

    /* Gradient Buttons */
    .stButton > button, .stDownloadButton > button {
        background: linear-gradient(90deg, #06b6d4, #6366f1, #ec4899);
        color: white !important;
        border: none;
        border-radius: 12px;
        font-weight: 700;
        padding: 0.5rem 1.2rem;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.55);
    }

    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background: rgba(255, 255, 255, 0.06);
        border-radius: 10px 10px 0 0;
        color: #cbd5e1;
        padding: 8px 18px;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(90deg, #06b6d4, #6366f1) !important;
        color: #ffffff !important;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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

st.markdown('<div class="hero-title">🌦️ India Live Weather & Air Quality</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-sub">Search any Indian State, City, or Village • Live Open-Meteo ETL Pipeline → SQLite → Auto-Refreshing Dashboard</div>',
    unsafe_allow_html=True,
)

# ---- Universal India Search Bar (Live Autocomplete + Click Suggestions + Autocorrect) ----
DEFAULT_SUGGESTIONS = [
    ("Delhi, Delhi", {"label": "Delhi, Delhi", "name": "Delhi", "lat": 28.6139, "lon": 77.2090}),
    ("Mumbai, Maharashtra", {"label": "Mumbai, Maharashtra", "name": "Mumbai", "lat": 19.0760, "lon": 72.8777}),
    ("Bengaluru, Karnataka", {"label": "Bengaluru, Karnataka", "name": "Bengaluru", "lat": 12.9716, "lon": 77.5946}),
    ("Hyderabad, Telangana", {"label": "Hyderabad, Telangana", "name": "Hyderabad", "lat": 17.3850, "lon": 78.4867}),
    ("Chennai, Tamil Nadu", {"label": "Chennai, Tamil Nadu", "name": "Chennai", "lat": 13.0827, "lon": 80.2707}),
    ("Yemmiganur, Kurnool, Andhra Pradesh", {"label": "Yemmiganur, Kurnool, Andhra Pradesh", "name": "Yemmiganur", "lat": 15.7720, "lon": 77.4800}),
    ("Visakhapatnam, Andhra Pradesh", {"label": "Visakhapatnam, Andhra Pradesh", "name": "Visakhapatnam", "lat": 17.6868, "lon": 83.2185}),
    ("Jaipur, Rajasthan", {"label": "Jaipur, Rajasthan", "name": "Jaipur", "lat": 26.9124, "lon": 75.7873}),
]


def _search_suggestions(searchterm: str):
    if not searchterm or len(searchterm.strip()) < 2:
        return DEFAULT_SUGGESTIONS
    matches = fetch_data.search_india_locations(searchterm)
    return [(m["label"], m) for m in matches]


chosen = st_searchbox(
    _search_suggestions,
    placeholder="🔍 Type any Indian State, City, Town, or Village (e.g., Yemmiganur, Jaipur, Shimla)...",
    default_options=DEFAULT_SUGGESTIONS,
    debounce=200,
    key="india_live_searchbox",
)

if chosen and isinstance(chosen, dict):
    with st.spinner(f"Fetching live weather & AQI for {chosen['label']}..."):
        try:
            live = fetch_data.fetch_current(chosen["label"], chosen["lat"], chosen["lon"])
            hist_rows = fetch_data.fetch_history(chosen["label"], chosen["lat"], chosen["lon"], days=2)
            hist_df = pd.DataFrame(hist_rows)
            hist_df["observed_at"] = pd.to_datetime(hist_df["observed_at"])

            aqi_val = live.get("us_aqi")
            aqi_cat = analysis.aqi_category(aqi_val)
            aqi_color = analysis.AQI_COLORS.get(aqi_cat, "#38bdf8")

            st.markdown(
                f"""
                <div class="search-card">
                    <h3 style="margin:0; color:#fff;">📍 {chosen['label']}</h3>
                    <p style="margin:4px 0 0 0; color:#cbd5e1; font-size:0.9rem;">
                        Lat: {chosen['lat']:.4f}, Lon: {chosen['lon']:.4f} &nbsp;|&nbsp;
                        Air Quality: <span style="background:{aqi_color}; color:#fff; padding:2px 10px; border-radius:12px; font-weight:700;">{aqi_cat}</span>
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            s1, s2, s3, s4, s5 = st.columns(5)
            s1.metric("Temperature", f"{live.get('temperature', 0):.1f} °C")
            s2.metric("Feels Like", f"{live.get('apparent_temp', 0):.1f} °C")
            s3.metric("Humidity", f"{live.get('humidity', 0):.0f} %")
            s4.metric("Wind Speed", f"{live.get('wind_speed', 0):.1f} km/h")
            s5.metric("US AQI", "n/a" if aqi_val is None else f"{aqi_val:.0f}")

            if not hist_df.empty:
                c_left, c_right = st.columns(2)
                with c_left:
                    fig_t = px.area(
                        hist_df, x="observed_at", y="temperature",
                        title=f"48h Temperature Trend — {chosen['name']}",
                        labels={"observed_at": "Time (IST)", "temperature": "°C"},
                        template="plotly_dark", height=280,
                    )
                    fig_t.update_traces(line_color="#38bdf8", fillcolor="rgba(56, 189, 248, 0.25)")
                    fig_t.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin={"l": 0, "r": 0, "t": 35, "b": 0})
                    st.plotly_chart(fig_t, use_container_width=True, key="search_temp_chart")
                with c_right:
                    fig_a = px.area(
                        hist_df, x="observed_at", y="us_aqi",
                        title=f"48h US AQI Trend — {chosen['name']}",
                        labels={"observed_at": "Time (IST)", "us_aqi": "US AQI"},
                        template="plotly_dark", height=280,
                    )
                    fig_a.update_traces(line_color="#e879f9", fillcolor="rgba(232, 121, 249, 0.25)")
                    fig_a.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin={"l": 0, "r": 0, "t": 35, "b": 0})
                    st.plotly_chart(fig_a, use_container_width=True, key="search_aqi_chart")
            st.divider()
        except Exception as exc:
            st.error(f"Could not fetch live data for {chosen['label']}: {exc}")
# ---- Interactive Click-to-Check Weather Map ----
with st.expander("🗺️ Interactive Map — Click Anywhere in India to Check Live Weather & AQI", expanded=False):
    st.caption("Pan, zoom, and click any state, city, or village on the map to fetch live conditions.")
    click_map = folium.Map(
        location=[22.5, 80.0],
        zoom_start=5,
        tiles="OpenStreetMap",
        attribution_control=False,
    )
    click_map.add_child(folium.LatLngPopup())

    for city_name, (clat, clon) in CITIES.items():
        folium.CircleMarker(
            location=[clat, clon],
            radius=5,
            color="#38bdf8",
            fill=True,
            fill_color="#818cf8",
            fill_opacity=0.85,
            tooltip=city_name,
        ).add_to(click_map)

    map_click = st_folium(
        click_map,
        height=430,
        use_container_width=True,
        returned_objects=["last_clicked"],
        key="interactive_weather_map",
    )

    if map_click and map_click.get("last_clicked"):
        lat = map_click["last_clicked"]["lat"]
        lon = map_click["last_clicked"]["lng"]
        place_name = fetch_data.reverse_geocode(lat, lon)

        with st.spinner(f"Fetching live weather & AQI for {place_name}..."):
            try:
                live_pt = fetch_data.fetch_current(place_name, lat, lon)
                hist_pt = pd.DataFrame(fetch_data.fetch_history(place_name, lat, lon, days=2))
                hist_pt["observed_at"] = pd.to_datetime(hist_pt["observed_at"])

                aqi_val = live_pt.get("us_aqi")
                aqi_cat = analysis.aqi_category(aqi_val)
                aqi_color = analysis.AQI_COLORS.get(aqi_cat, "#38bdf8")

                st.markdown(
                    f"""
                    <div class="search-card">
                        <h3 style="margin:0; color:#fff;">📍 {place_name}</h3>
                        <p style="margin:4px 0 0 0; color:#cbd5e1; font-size:0.9rem;">
                            Lat: {lat:.4f}, Lon: {lon:.4f} &nbsp;|&nbsp;
                            Air Quality: <span style="background:{aqi_color}; color:#fff; padding:2px 10px; border-radius:12px; font-weight:700;">{aqi_cat}</span>
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Temperature", f"{live_pt.get('temperature', 0):.1f} °C")
                m2.metric("Feels Like", f"{live_pt.get('apparent_temp', 0):.1f} °C")
                m3.metric("Humidity", f"{live_pt.get('humidity', 0):.0f} %")
                m4.metric("Wind Speed", f"{live_pt.get('wind_speed', 0):.1f} km/h")
                m5.metric("US AQI", "n/a" if aqi_val is None else f"{aqi_val:.0f}")

                if not hist_pt.empty:
                    mc1, mc2 = st.columns(2)
                    with mc1:
                        ft = px.area(
                            hist_pt, x="observed_at", y="temperature",
                            title=f"48h Temperature — {place_name}",
                            labels={"observed_at": "Time (IST)", "temperature": "°C"},
                            template="plotly_dark", height=260,
                        )
                        ft.update_traces(line_color="#38bdf8", fillcolor="rgba(56, 189, 248, 0.25)")
                        ft.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin={"l": 0, "r": 0, "t": 35, "b": 0})
                        st.plotly_chart(ft, use_container_width=True, key="map_click_temp")
                    with mc2:
                        fa = px.area(
                            hist_pt, x="observed_at", y="us_aqi",
                            title=f"48h US AQI — {place_name}",
                            labels={"observed_at": "Time (IST)", "us_aqi": "US AQI"},
                            template="plotly_dark", height=260,
                        )
                        fa.update_traces(line_color="#e879f9", fillcolor="rgba(232, 121, 249, 0.25)")
                        fa.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin={"l": 0, "r": 0, "t": 35, "b": 0})
                        st.plotly_chart(fa, use_container_width=True, key="map_click_aqi")
            except Exception as exc:
                st.error(f"Could not fetch live data for this location: {exc}")



# ---- Sidebar Controls ----
with st.sidebar:
    st.header("⚙️ Dashboard Filters")
    selected = st.multiselect("Tracked Major Cities", list(CITIES), default=list(CITIES))
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
    fetch_data.collect_if_stale()

    df = db.read_readings(window_hours)
    df = df[df["city"].isin(cities)]
    if df.empty:
        st.info("No data yet. Check your internet connection, then click 'Fetch latest data now'.")
        return

    snap = analysis.latest_snapshot(df)
    snap["lat"] = snap["city"].map(lambda c: CITIES[c][0])
    snap["lon"] = snap["city"].map(lambda c: CITIES[c][1])

    # ---- KPI row ----
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Avg temperature", f"{snap['temperature'].mean():.1f} °C")
    k2.metric("Avg humidity", f"{snap['humidity'].mean():.0f} %")
    aqi_mean = snap["us_aqi"].mean()
    k3.metric("Avg US AQI", "n/a" if pd.isna(aqi_mean) else f"{aqi_mean:.0f}")
    k4.metric("Latest reading (IST)", snap["observed_at"].max().strftime("%d %b, %H:%M"))

    tab1, tab2, tab3 = st.tabs(["📍 Overview", "📈 Trends", "🛠️ Data & pipeline"])

    # ---- Overview ----
    with tab1:
        left, right = st.columns([3, 2])
        with left:
            fig = px.scatter_map(
                snap, lat="lat", lon="lon", color="aqi_category",
                color_discrete_map=analysis.AQI_COLORS, hover_name="city",
                hover_data={"temperature": ":.1f", "humidity": ":.0f", "us_aqi": ":.0f",
                            "lat": False, "lon": False, "aqi_category": False},
                zoom=3.4, center={"lat": 22.0, "lon": 80.0}, height=470,
                map_style="carto-darkmatter",
            )
            fig.update_traces(marker={"size": 16})
            fig.update_layout(
                margin={"l": 0, "r": 0, "t": 0, "b": 0},
                legend_title_text="AQI level",
                paper_bgcolor="rgba(0,0,0,0)",
                font={"color": "#f8fafc"},
            )
            st.plotly_chart(fig, key="map_chart", use_container_width=True)
        with right:
            bar = px.bar(
                snap.sort_values("us_aqi"), x="us_aqi", y="city", orientation="h",
                color="aqi_category", color_discrete_map=analysis.AQI_COLORS,
                labels={"us_aqi": "US AQI", "city": ""}, height=470,
                template="plotly_dark",
            )
            bar.update_layout(
                showlegend=False,
                margin={"l": 0, "r": 0, "t": 35, "b": 0},
                title="Air quality by city",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(bar, key="aqi_bar", use_container_width=True)

        st.subheader("✨ Key insights")
        for line in analysis.build_insights(snap, df):
            st.markdown(f"- {line}")

        st.subheader("📋 Latest snapshot")
        table = snap[["city", "temperature", "apparent_temp", "humidity", "wind_speed",
                      "precipitation", "us_aqi", "aqi_category", "pm2_5", "pm10"]].copy()
        table.columns = ["City", "Temp °C", "Feels like °C", "Humidity %", "Wind km/h",
                         "Rain mm", "US AQI", "AQI level", "PM2.5", "PM10"]
        st.dataframe(table.round(1), hide_index=True, use_container_width=True)

    # ---- Trends ----
    with tab2:
        label = st.selectbox("Metric", list(METRICS), key="trend_metric")
        col = METRICS[label]
        line = px.line(
            df, x="observed_at", y=col, color="city",
            labels={"observed_at": "Time (IST)", col: label, "city": "City"},
            height=420, template="plotly_dark",
        )
        line.update_layout(
            margin={"l": 0, "r": 0, "t": 10, "b": 0},
            hovermode="x unified",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(line, key="trend_line", use_container_width=True)

        heat = (
            df.assign(hour=df["observed_at"].dt.floor("h"))
            .pivot_table(index="city", columns="hour", values=col, aggfunc="mean")
        )
        if not heat.empty:
            hm = px.imshow(
                heat, aspect="auto", color_continuous_scale="Plasma",
                labels={"x": "Hour", "y": "", "color": label},
                height=360, template="plotly_dark",
            )
            hm.update_layout(
                margin={"l": 0, "r": 0, "t": 35, "b": 0},
                title=f"{label}: city x hour heatmap",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(hm, key="trend_heatmap", use_container_width=True)

    # ---- Pipeline ----
    with tab3:
        log = db.read_log(50)
        p1, p2, p3 = st.columns(3)
        p1.metric("Rows stored", f"{db.count_readings():,}")
        success = (log["status"] == "ok").mean() * 100 if not log.empty else 0
        p2.metric("Fetch success rate (last 50)", f"{success:.0f} %")
        p3.metric("Cities tracked", len(CITIES))
        st.subheader("Recent fetch log")
        st.dataframe(log.head(15), hide_index=True, use_container_width=True)
        st.download_button(
            "⬇️ Download data as CSV (use it in Power BI / Excel)",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="weather_air_quality.csv",
            mime="text/csv",
            key="csv_download",
        )

    st.caption("Weather data: Open-Meteo.com (CC BY 4.0). Air quality: CAMS ENSEMBLE / Copernicus via Open-Meteo.")


live_dashboard(selected, hours)