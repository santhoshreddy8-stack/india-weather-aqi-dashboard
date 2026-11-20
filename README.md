# 🌦️ India Live Weather & Air Quality Dashboard

An end-to-end, auto-refreshing ETL pipeline and interactive analytics dashboard that tracks live weather and air quality metrics across 8 major Indian cities. Built with **Python, SQLite, Pandas, Plotly, and Streamlit**.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.40%2B-FF4B4B?logo=streamlit&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-5.24%2B-3F4F75?logo=plotly&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-WAL%20Mode-003B57?logo=sqlite&logoColor=white)

🔗 **Live App:** `[https://india-weather-aqi-dashboard.streamlit.app/]`  
🎥 **Demo Video:** `[Add your YouTube / LinkedIn demo link here]`

---

## 🏗️ System Architecture

```text
┌─────────────────────────┐      HTTP / Retry      ┌──────────────────────────┐
│     Open-Meteo APIs     │ ─────────────────────► │  Python ETL Collector    │
│  (Weather + Air Quality)│                        │     (fetch_data.py)      │
└─────────────────────────┘                        └────────────┬─────────────┘
                                                                │ Deduplicated Upsert
                                                                ▼
┌─────────────────────────┐      Read & Query      ┌──────────────────────────┐
│   Streamlit Dashboard   │ ◄───────────────────── │     SQLite Database      │
│ (Plotly + Auto-Refresh) │                        │   (data/weather.db WAL)  │
└─────────────────────────┘                        └──────────────────────────┘
```
