import os
import streamlit as st
import pandas as pd
import requests
import random
import re
import json
import hashlib
from datetime import datetime, timedelta
from io import StringIO

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

st.set_page_config(page_title="🎬 IMDb Random Picker", layout="centered")

OMDB_API_KEY = os.getenv("OMDB_API_KEY")
if not OMDB_API_KEY:
    st.error("❌ Geen OMDB_API_KEY gevonden. Stel deze in als environment variable.")
    st.stop()

# ------------------------------
# 🗂️ CACHE SYSTEEM
# ------------------------------
CACHE_FILE = "movie_cache.json"
CACHE_TTL_DAYS = 30

def get_cache_key(imdb_ids):
    """Maak unieke key voor watchlist gebaseerd op IMDb IDs"""
    sorted_ids = sorted(imdb_ids)
    return hashlib.md5(''.join(sorted_ids).encode()).hexdigest()

def load_cache():
    """Laad cache van lokaal JSON bestand"""
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "cache_metadata": {
                "version": "1.0",
                "created": datetime.now().isoformat()
            },
            "individual_movies": {},
            "watchlists": {}
        }

def save_cache(cache):
    """Sla cache op in lokaal JSON bestand"""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Cache save error: {e}")
        return False

def is_cache_valid(timestamp_str, ttl_days=CACHE_TTL_DAYS):
    """Controleer of cache item nog geldig is"""
    try:
        timestamp = datetime.fromisoformat(timestamp_str)
        expiry_date = timestamp + timedelta(days=ttl_days)
        return datetime.now() < expiry_date
    except:
        return False

def get_cached_movie_data(imdb_ids):
    """Haal films op uit cache of van OMDb API"""
    cache = load_cache()
    cache_key = get_cache_key(imdb_ids)
    
    # Check of complete watchlist gecached is en nog geldig
    if cache_key in cache.get("watchlists", {}):
        watchlist_data = cache["watchlists"][cache_key]
        if is_cache_valid(watchlist_data.get("created", "")):
            st.info("📁 Watchlist geladen uit cache")
            return watchlist_data["movies_data"]
        else:
            # 🔥 CRITIEKE FIX: Verwijder expired watchlist uit cache
            del cache["watchlists"][cache_key]
            save_cache(cache)
            st.info("🔄 Cache verlopen, nieuwe data ophalen...")
    
    # Nieuwe films ophalen
    movies_data = []
    new_movies_count = 0
    
    with st.spinner("Films ophalen (cache systeem)..."):
        progress = st.progress(0)
        
        for i, imdb_id in enumerate(imdb_ids):
            # Check individuele film cache
            cached_movie = cache.get("individual_movies", {}).get(imdb_id)
            if cached_movie and is_cache_valid(cached_movie.get("last_fetched", "")):
                movies_data.append((imdb_id, cached_movie["data"]))
            else:
                # Nieuwe film ophalen van OMDb
                movie_data = get_movie_data_uncached(imdb_id)
                if movie_data:
                    movies_data.append((imdb_id, movie_data))
                    new_movies_count += 1
                    
                    # Update individuele cache
                    if "individual_movies" not in cache:
                        cache["individual_movies"] = {}
                    cache["individual_movies"][imdb_id] = {
                        "data": movie_data,
                        "last_fetched": datetime.now().isoformat(),
                        "ttl_days": CACHE_TTL_DAYS
                    }
            
            progress.progress((i + 1) / len(imdb_ids))
        
        progress.empty()
    
    # Sla complete watchlist op
    if "watchlists" not in cache:
        cache["watchlists"] = {}
    
    cache["watchlists"][cache_key] = {
        "imdb_ids": imdb_ids,
        "movies_data": movies_data,
        "created": datetime.now().isoformat(),
        "movie_count": len(movies_data),
        "new_movies_added": new_movies_count
    }
    
    save_cache(cache)
    
    if new_movies_count > 0:
        st.success(f"✅ {new_movies_count} nieuwe films toegevoegd aan cache")
    
    return movies_data

# ------------------------------
# 🔎 Extract IMDb IDs
# ------------------------------
@st.cache_data(show_spinner=False)
def extract_imdb_ids(df):
    imdb_ids = set()
    pattern = re.compile(r'(tt\d{7,8})')
    for col in df.columns:
        try:
            matches = df[col].astype(str).str.extractall(pattern)[0].unique()
            for match in matches:
                if pd.notna(match):
                    imdb_ids.add(match)
        except:
            continue
    return list(imdb_ids)

# ------------------------------
# 🎬 Fetch OMDb data (zonder cache)
# ------------------------------
def get_movie_data_uncached(imdb_id):
    try:
        # Eerst proberen in het Nederlands
        url_nl = f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}&plot=full&language=nl"
        response_nl = requests.get(url_nl, timeout=10)
        response_nl.raise_for_status()
        data_nl = response_nl.json()
        
        if data_nl.get('Response') == 'True' and data_nl.get('Plot') and data_nl.get('Plot') != 'N/A':
            return data_nl
        else:
            # Fallback naar Engels
            url_en = f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}&plot=full"
            response_en = requests.get(url_en, timeout=10)
            response_en.raise_for_status()
            data_en = response_en.json()
            return data_en if data_en.get('Response') == 'True' else {}
    except:
        return {}

# ------------------------------
# 🍅 Rotten Tomatoes extractor
# ------------------------------
def extract_rotten_tomatoes_score(movie):
    for rate in movie.get("Ratings", []):
        if rate.get("Source") == "Rotten Tomatoes":
            return rate.get("Value")
    return "N/A"

# ------------------------------
# 🎥 Find YouTube trailer
# ------------------------------
def find_youtube_trailer(title, year):
    try:
        query = f"{title} {year} official trailer site:youtube.com"
        search_url = f"https://www.youtube.com/results?search_query={requests.utils.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(search_url, headers=headers, timeout=15)
        video_ids = re.findall(r'watch\?v=(\S{11})', response.text)
        if video_ids:
            return f"https://www.youtube.com/watch?v={video_ids[0]}"
        return None
    except:
        return None
    
# 🔞 IMDb Parental Guide: Sex & Nudity (gefixed)
@st.cache_data(show_spinner=False, ttl=3600)
def get_sex_nudity_rating(imdb_id):
    """
    Scrapet de IMDb Parental Guide pagina en haalt de 'Sex & Nudity' categorie op.
    Mogelijke waarden:
        - None
        - Mild
        - Moderate
        - Severe
    """
    try:
        url = f"https://www.imdb.com/title/{imdb_id}/parentalguide"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }
        r = requests.get(url, headers=headers, timeout=12)
        r.raise_for_status()
        html = r.text

        # Verbeterde regex patterns voor verschillende IMDb layouts
        patterns = [
            # Nieuwe IMDb layout met data-testid
            r'data-testid="advisory-severity-item-SEX_AND_NUDITY"[^>]*>\s*<span[^>]*>(Mild|Moderate|Severe|None)</span',
            # Alternatieve layout
            r'Sex & Nudity</h4>[^>]*>([^<]*)</div',
            # Oudere layout
            r'<h4>Sex & Nudity</h4>\s*<div[^>]*>\s*([^<]+)\s*</div',
            # Fallback: zoek naar seks & nudity ergens in de section
            r'Sex[^>]*Nudity[^>]*?(Mild|Moderate|Severe|None)',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                rating = match.group(1).strip().capitalize()
                if rating in ['Mild', 'Moderate', 'Severe', 'None']:
                    return rating

        # Als we niets vinden met regex, proberen we een andere aanpak
        if "Sex & Nudity" in html:
            # Kijk of we de rating kunnen vinden in de buurt van de sectie
            sex_section = html.split("Sex & Nudity")[1][:1000] if "Sex & Nudity" in html else ""
            for level in ['Severe', 'Moderate', 'Mild', 'None']:
                if level.lower() in sex_section.lower():
                    return level

        return "Onbekend"
        
    except requests.RequestException:
        return "Onbekend (timeout)"
    except Exception as e:
        return f"Onbekend (error: {str(e)})"

# ------------------------------
# 🚀 UI
# ------------------------------
st.title("🎬 IMDb Random Picker")
st.markdown("Upload een CSV-bestand met IMDb ID's (zoals `tt1234567`). Werkt met watchlists of elke CSV met IDs.")

with st.expander("📋 Voorbeeld CSV-formaat"):
    st.code("""Const,Title,Year\ntt0111161,The Shawshank Redemption,1994\ntt0068646,The Godfather,1972\ntt0071562,The Godfather Part II,1974""")

uploaded_file = st.file_uploader("📤 Upload CSV-bestand", type=["csv"])

if uploaded_file:
    try:
        # CSV inladen
        try:
            df = pd.read_csv(uploaded_file)
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            content = uploaded_file.read().decode('latin-1')
            df = pd.read_csv(StringIO(content))

        imdb_ids = extract_imdb_ids(df)
        if not imdb_ids:
            st.warning("⚠️ Geen IMDb ID's gevonden.")
            st.stop()

        st.success(f"✅ {len(imdb_ids)} IMDb ID's gevonden!")
        media_type = st.selectbox("📺 Wat wil je kijken?", ["Alles", "Alleen films", "Alleen series"])

        # ---------- Data ophalen MET CACHE ----------
        rebuild = False
        if "all_data" not in st.session_state:
            rebuild = True
        elif st.session_state.get("last_media_type") != media_type:
            rebuild = True
        elif st.session_state.get("last_imdb_ids") != imdb_ids:
            rebuild = True

        if rebuild:
            st.session_state.last_imdb_ids = imdb_ids
            st.session_state.last_media_type = media_type
            
            # Gebruik cache systeem
            all_movies_data = get_cached_movie_data(imdb_ids)
            
            # Filter op media type
            if media_type == "Alleen films":
                st.session_state.all_data = [
                    item for item in all_movies_data if item[1].get("Type") == "movie"
                ]
            elif media_type == "Alleen series":
                st.session_state.all_data = [
                    item for item in all_movies_data if item[1].get("Type") == "series"
                ]
            else:
                st.session_state.all_data = all_movies_data

        if not st.session_state.all_data:
            st.warning("⚠️ Geen titels gevonden met dat type.")
            st.stop()

        # ---------- Random selectie ----------
        if "available_indices" not in st.session_state:
            st.session_state.available_indices = list(range(len(st.session_state.all_data)))
            random.shuffle(st.session_state.available_indices)
        
        if "last_selected_idx" not in st.session_state:
            if st.session_state.available_indices:
                st.session_state.last_selected_idx = st.session_state.available_indices.pop()
            else:
                # Reset als alle films zijn getoond
                st.session_state.available_indices = list(range(len(st.session_state.all_data)))
                random.shuffle(st.session_state.available_indices)
                st.session_state.last_selected_idx = st.session_state.available_indices.pop()

        if st.button("🔁 Nieuwe selectie", type="primary"):
            if st.session_state.available_indices:
                st.session_state.last_selected_idx = st.session_state.available_indices.pop()
            else:
                # Reset en shuffle opnieuw als alle films zijn getoond
                st.session_state.available_indices = list(range(len(st.session_state.all_data)))
                random.shuffle(st.session_state.available_indices)
                st.session_state.last_selected_idx = st.session_state.available_indices.pop()

        chosen_id, movie = st.session_state.all_data[st.session_state.last_selected_idx]

        trailer_url = find_youtube_trailer(movie.get('Title'), movie.get('Year'))

        # ---------- UI ----------
        st.subheader(f"{movie.get('Title', 'Onbekende titel')} ({movie.get('Year', '?')})")

        col1, col2 = st.columns([1, 2])
        with col1:
            poster = movie.get('Poster')
            if poster and poster != "N/A":
                st.image(poster, width=200)
            else:
                st.warning("Geen poster beschikbaar")

        with col2:
            st.markdown(f"**🎞️ Type:** {movie.get('Type', 'Onbekend').capitalize()}")
            st.markdown(f"**🎬 Regisseur:** {movie.get('Director', 'Onbekend')}")

            cast = movie.get('Actors', 'Onbekend')
            if cast and cast != "N/A":
                st.markdown("**🌟 Hoofdrolspelers:**")
                for actor in cast.split(','):
                    st.markdown(f"- {actor.strip()}")
            else:
                st.markdown("**🌟 Hoofdrolspelers:** Geen cast data")

            # ⭐ IMDb + 🍅 Rotten Tomatoes
            st.markdown(f"**⭐ IMDb Rating:** {movie.get('imdbRating', 'N/A')}")
            rt_score = extract_rotten_tomatoes_score(movie)
            st.markdown(f"**🍅 Rotten Tomatoes:** {rt_score}")

            st.markdown(f"**⏳ Looptijd:** {movie.get('Runtime', 'Onbekend')}")
            st.markdown(f"**🎭 Genre:** {movie.get('Genre', 'Onbekend')}")
            sex_rating = get_sex_nudity_rating(chosen_id)
            st.markdown(f"**🔞 Sex & Nudity:** {sex_rating}")

            # 🔗 IMDb pagina
            st.markdown(f"[⭐ IMDb](https://www.imdb.com/title/{chosen_id}/)")

            # 🍅 Rotten Tomatoes pagina (via zoekopdracht)
            rt_query = f"{movie.get('Title', '')} {movie.get('Year', '')}"
            rt_url = f"https://www.rottentomatoes.com/search?search={requests.utils.quote(rt_query)}"
            st.markdown(f"[🍅 Rotten Tomatoes]({rt_url})")

            # 📖 Verhaal (NU BOVEN de trailer)
            st.markdown(f"**📖 Verhaal:**  \n{movie.get('Plot', 'Geen beschrijving beschikbaar')}")

            # 🎥 Trailer (NU ONDER het verhaal)
            if trailer_url:
                st.video(trailer_url)
            else:
                st.warning("Geen trailer gevonden")

    except Exception as e:
        st.error(f"❌ Fout bij verwerken bestand: {str(e)}")