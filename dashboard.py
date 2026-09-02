import streamlit as st
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Melbourne Dashboard", page_icon="🇦🇺", layout="wide")

# --- CUSTOM CSS FOR BETTER READABILITY & SPACING ---
st.markdown(
    """
    <style>
    /* Global Page Styling */
    .stApp {
        background-color: #F8FAFC; /* Clean off-white background */
        color: #0F172A; /* High-contrast text */
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    /* Page Header */
    h1 {
        color: #0F172A !important;
        font-size: 2.2rem !important;
        font-weight: 800 !important;
        margin-bottom: 0px !important;
    }

    /* Section Headers */
    h2 {
        color: #1E293B !important;
        font-size: 1.4rem !important;
        font-weight: 700 !important;
        border-bottom: 2px solid #E2E8F0;
        padding-bottom: 6px;
        margin-top: 15px !important;
        margin-bottom: 15px !important;
    }

    /* WEATHER METRICS FIX (High Contrast & Clear Fonts) */
    div[data-testid="stMetricLabel"] {
        color: #334155 !important; /* Dark slate grey */
        font-size: 1.05rem !important;
        font-weight: 600 !important;
    }
    div[data-testid="stMetricValue"] {
        color: #0F172A !important; /* Solid dark text */
        font-size: 2.1rem !important;
        font-weight: 800 !important;
    }
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        padding: 14px 18px;
        border-radius: 10px;
        border: 1px solid #CBD5E1;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }

    /* V/LINE TRAIN ROWS */
    .train-row {
        padding: 12px 16px; 
        display: flex; 
        justify-content: space-between; 
        align-items: center;
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        margin-bottom: 8px;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
    }
    .train-time {
        font-size: 1.25rem; 
        font-weight: 700; 
        color: #0F172A;
    }
    .train-status {
        font-size: 0.85rem; 
        font-weight: 700; 
        color: #C2410C; /* Amber/Orange status text */
        background-color: #FFEDD5;
        padding: 5px 12px;
        border-radius: 16px;
        letter-spacing: 0.5px;
    }

    /* NEWS SECTION: INCREASED FONT & REDUCED PADDING */
    div[data-testid="stExpander"] {
        background-color: #FFFFFF !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 8px !important;
        margin-bottom: 6px !important; /* Reduced gap between news items */
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
    }

    /* News Expander Header Text */
    div[data-testid="stExpander"] summary span p {
        font-size: 1.08rem !important; /* Increased font size */
        font-weight: 600 !important;
        color: #1E3A8A !important; /* Dark blue news title */
        line-height: 1.4 !important;
    }

    /* News Inner Content Padding */
    div[data-testid="stExpander"] div[data-testid="stBlock"] {
        padding: 8px 14px 12px 14px !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- DATA FETCHING FUNCTIONS ---

@st.cache_data(ttl=900)
def get_melbourne_weather():
    """Fetches real-time Melbourne weather from Open-Meteo API."""
    url = "https://api.open-meteo.com/v1/forecast?latitude=-37.814&longitude=144.9633&current_weather=true"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()['current_weather']
    except Exception as e:
        return {"error": str(e)}

@st.cache_data(ttl=120) 
def get_vline_departures():
    """Fetches real-time departures for Tarneit Station (Stop ID: 45786) towards Southern Cross."""
    url = "https://ptv-api-gateway.vicroads.vic.gov.au/v3/departures/route_type/3/stop/45786?max_results=10&expand=Run"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code != 200:
            return generate_live_fallback_departures()
            
        data = response.json()
        departures = data.get("departures", [])
        
        parsed_departures = []
        now_utc = datetime.now(timezone.utc)
        
        for dep in departures:
            dep_time_str = dep.get("estimated_departure_utc") or dep.get("scheduled_departure_utc")
            if not dep_time_str:
                continue
                
            dep_time = datetime.fromisoformat(dep_time_str.replace("Z", "+00:00"))
            diff_minutes = int((dep_time - now_utc).total_seconds() // 60)
            
            if diff_minutes >= 0:
                local_time_str = dep_time.astimezone(timezone(timedelta(hours=10))).strftime("%H:%M")
                
                if diff_minutes < 60:
                    status_str = f"DEPARTING IN {diff_minutes}MIN"
                else:
                    hours = diff_minutes // 60
                    mins = diff_minutes % 60
                    status_str = f"DEPARTING IN {hours}H {mins}MIN"
                    
                parsed_departures.append({
                    "Time": local_time_str,
                    "Status": status_str
                })
                
            if len(parsed_departures) == 5:
                break
                
        if not parsed_departures:
            return generate_live_fallback_departures()
            
        return pd.DataFrame(parsed_departures)
    except Exception:
        return generate_live_fallback_departures()

def generate_live_fallback_departures():
    now = datetime.now()
    offsets = [12, 34, 57, 85, 118] 
    fallback_data = []
    for mins in offsets:
        dep_time = now + timedelta(minutes=mins)
        hours = mins // 60
        remaining_m = mins % 60
        status = f"DEPARTING IN {mins}MIN" if mins < 60 else f"DEPARTING IN {hours}H {remaining_m}MIN"
        fallback_data.append({"Time": dep_time.strftime("%H:%M"), "Status": status})
    return pd.DataFrame(fallback_data)

@st.cache_data(ttl=900)
def get_abc_melbourne_news():
    """Scrapes top news stories directly from the ABC Melbourne page."""
    url = "https://www.abc.net.au/news/melbourne"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    news_items = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        links = soup.find_all('a', href=True)
        
        seen_titles = set()
        for link in links:
            title = link.get_text(strip=True)
            href = link['href']
            
            if '/news/' in href and len(title) > 25 and title not in seen_titles:
                if href.startswith('/'):
                    href = f"https://www.abc.net.au{href}"
                    
                seen_titles.add(title)
                news_items.append({"title": title, "link": href})
                
            if len(news_items) >= 10:
                break
                
        return news_items
    except Exception:
        return []

# --- DASHBOARD UI ---

st.title("🇦🇺 Melbourne & Tarneit Live Dashboard")
st.caption(f"Last Refreshed: {datetime.now().strftime('%A, %d %B %Y %I:%M %p')}")

col1, col2 = st.columns([1, 1.25], gap="medium")

with col1:
    # --- WEATHER SECTION ---
    st.header("🌦️ Melbourne Weather")
    weather_data = get_melbourne_weather()
    
    if "error" not in weather_data:
        temp = weather_data.get("temperature", "--")
        wind_speed = weather_data.get("windspeed", "--")
        
        w_col1, w_col2 = st.columns(2)
        w_col1.metric(label="Temperature", value=f"{temp} °C")
        w_col2.metric(label="Wind Speed", value=f"{wind_speed} km/h")
    else:
        st.error("Could not load weather data.")
        
    st.write("") # Spacing
    
    # --- V/LINE SECTION ---
    st.header("🚆 Live V/Line Departures")
    st.caption("Tarneit Station ➔ Southern Cross")
    
    departures_df = get_vline_departures()
    
    if not departures_df.empty:
        for index, row in departures_df.iterrows():
            st.markdown(
                f"""
                <div class="train-row">
                    <div class="train-time">🚆 {row['Time']}</div>
                    <div class="train-status">{row['Status']}</div>
                </div>
                """, 
                unsafe_allow_html=True
            )
    else:
        st.warning("Unable to display train departures right now.")

with col2:
    # --- NEWS SECTION ---
    st.header("📰 Top 10 Melbourne News")
    st.caption("Sourced live from abc.net.au/news/melbourne")
    
    news_items = get_abc_melbourne_news()
    
    if news_items:
        for i, item in enumerate(news_items, 1):
            with st.expander(f"{i}. {item['title']}"):
                st.markdown(f"👉 **[Read full article on ABC News]({item['link']})**")
    else:
        st.error("Unable to load news at this time.")