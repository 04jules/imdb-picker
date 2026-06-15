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
from upstash_redis import Redis

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
# 🗂️ PERMANENTE CLOUD CACHE (Upstash Redis)
# ------------------------------
REDIS_URL = os.getenv("UPSTASH_REDIS_REST_URL")
REDIS_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

if REDIS_URL and REDIS_TOKEN:
    try:
        redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
        use_redis = True
    except Exception as e:
        st.error(f"❌ Fout bij initialiseren Upstash verbinding: {str(e)}")
        use_redis = False
else:
    st.warning("⚠️ Upstash Redis variabelen niet gevonden. App draait zonder permanente cache.")
    use_redis = False

CACHE_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 dagen

def get_movie_data_uncached(imdb_id):
    """Haal film op van OMDb (Nederlands met Engelse fallback)"""
    try:
        url_nl = f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}&plot=full&language=nl"
        response_nl = requests.get(url_nl, timeout=10)
        response_nl.raise_for_status()
        data_nl = response_nl.json()
        
        if data_nl.get('Response') == 'True' and data_nl.get('Plot') and data_nl.get('Plot') != 'N/A':
            return data_nl
        else:
            url_en = f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}&plot=full"
            response_en = requests.get(url_en, timeout=10)
            response_en.raise_for_status()
            data_en = response_en.json()
            return data_en if data_en.get('Response') == 'True' else {}
    except Exception as e:
        print(f"OMDb Fetch Error voor {imdb_id}: {e}")
        return {}

def get_cached_movie_data(imdb_ids):
    """Haal films op uit de permanente Upstash Cloud Cache of van OMDb"""
    movies_data = []
    new_movies_count = 0
    redis_errors = []
    
    with st.spinner("Films ophalen via permanente Cloud Cache..."):
        progress = st.progress(0)
        
        for i, imdb_id in enumerate(imdb_ids):
            movie_data = None
            
            # 1. Probeer eerst uit Upstash Redis te halen
            if use_redis:
                try:
                    cached_data = redis.get(f"movie:{imdb_id}")
                    if cached_data:
                        movie_data = json.loads(cached_data)
                except Exception as e:
                    error_msg = f"Leesfout voor {imdb_id}: {str(e)}"
                    if error_msg not in redis_errors:
                        redis_errors.append(error_msg)

            # 2. Niet in de cache gevonden? Haal live op bij OMDb
            if not movie_data:
                movie_data = get_movie_data_uncached(imdb_id)
                if movie_data and movie_data.get('Response') == 'True':
                    movies_data.append((imdb_id, movie_data))
                    new_movies_count += 1
                    
                    # Sla het direct op in Upstash
                    if use_redis:
                        try:
                            serialized_data = json.dumps(movie_data)
                            redis.set(f"movie:{imdb_id}", serialized_data, ex=CACHE_TTL_SECONDS)
                        except Exception as e:
                            error_msg = f"Schrijffout voor {imdb_id}: {str(e)}"
                            if error_msg not in redis_errors:
                                redis_errors.append(error_msg)
            else:
                movies_data.append((imdb_id, movie_data))
                
            progress.progress((i + 1) / len(imdb_ids))
            
        progress.empty()
        
    if redis_errors:
        st.error("⚠️ Er ging iets mis met de Upstash Cloud Cache verbinding:")
        for err in redis_errors[:5]:
            st.code(err)
        
    if new_movies_count > 0 and use_redis:
        st.success(f"✅ {new_movies_count} nieuwe films succesvol toegevoegd aan de permanente cloud cache!")
    elif use_redis and not redis_errors:
        st.info("ℹ️ Alle films stonden al veilig in de cloud cache!")
        
    return movies_data

# ------------------------------
# 🔎 Extract IMDb IDs (CACHE VERWIJDERD OM STREAMLIT BLOKKADE TE OMZEILEN)
# ------------------------------
def extract_imdb_ids(df):
    imdb_ids = set()
    pattern = re.compile(r'(tt\d{7,10})')
    for col in df.columns:
        try:
            for cell in df[col].astype(str):
                matches = pattern.findall(cell)
                for match in matches:
                    imdb_ids.add(match)
        except:
            continue
    return list(imdb_ids)

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
    
# 🔞 IMDb Parental Guide: Sex & Nudity (Slimme fix voor films én series via JSON + Regex fallbacks)
@st.cache_data(show_spinner=False, ttl=3600)
def get_sex_nudity_rating(imdb_id):
    try:
        url = f"https://www.imdb.com/title/{imdb_id}/parentalguide"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        r = requests.get(url, headers=headers, timeout=12)
        r.raise_for_status()
        html = r.text

        # 1. Probeer via de ingebedde Next.js JSON boomstructuur
        json_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
        if json_match:
            data = json.loads(json_match.group(1))
            queries = data.get("props", {}).get("pageProps", {}).get("aboveTheFoldData", {})
            if not queries:
                 queries = data.get("props", {}).get("pageProps", {}).get("mainColumnData", {})
            
            advisories = queries.get("parentsGuide", {}).get("advisories", {}).get("edges", [])
            for edge in advisories:
                node = edge.get("node", {})
                if node.get("advisoryCategory") == "SEX_AND_NUDITY":
                    severity = node.get("severity", {}).get("text")
                    if severity:
                        return severity.strip().capitalize()

        # 2. Uitgebreide Regex fallbacks (scant de hele HTML-pagina op labels voor films/series)
        patterns = [
            r'data-testid="advisory-severity-item-SEX_AND_NUDITY"[^>]*>\s*<span[^>]*>(Mild|Moderate|Severe|None)</span',
            r'Sex & Nudity</h4>[^>]*>\s*<span[^>]*>([^<]*)</span',
            r'Sex & Nudity</h4>[^>]*>([^<]*)</div',
            r'id="advisory-sexAndNudity"[^>]*?(Mild|Moderate|Severe|None)',
            r'Sex[^>]*Nudity[^>]*?(Mild|Moderate|Severe|None)',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                res = match.group(1).strip().capitalize()
                if res in ['Mild', 'Moderate', 'Severe', 'None']:
                    return res

        # 3. Specifieke check voor series die geen hoofd-label hebben maar wel een gevulde sectie
        if "Sex & Nudity" in html:
            sex_section = html.split("Sex & Nudity")[1][:1200]
            for level in ['Severe', 'Moderate', 'Mild', 'None']:
                if level.lower() in sex_section.lower():
                    return level

        return "None" # Als er echt niks te vinden is, is het meestal veilig/clean
        
    except Exception:
        return "Onbekend"

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

        st.success(f"✅ {len(imdb_ids)} unieke IMDb ID's gevonden in het bestand!")
        media_type = st.selectbox("📺 Wat wil je kijken?", ["Alles", "Alleen films", "Alleen series"])

        # ---------- Data ophalen ----------
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
            
            all_movies_data = get_cached_movie_data(imdb_ids)
            
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
            st.balloons()
        
        if "last_selected_idx" not in st.session_state:
            if st.session_state.available_indices:
                st.session_state.last_selected_idx = st.session_state.available_indices.pop()
            else:
                st.session_state.available_indices = list(range(len(st.session_state.all_data)))
                random.shuffle(st.session_state.available_indices)
                st.session_state.last_selected_idx = st.session_state.available_indices.pop()

        if st.button("🔁 Nieuwe selectie", type="primary"):
            if st.session_state.available_indices:
                st.session_state.last_selected_idx = st.session_state.available_indices.pop()
            else:
                st.session_state.available_indices = list(range(len(st.session_state.all_data)))
                random.shuffle(st.session_state.available_indices)
                st.session_state.last_selected_idx = st.session_state.available_indices.pop()
            st.balloons()

        chosen_id, movie = st.session_state.all_data[st.session_state.last_selected_idx]
        trailer_url = find_youtube_trailer(movie.get('Title'), movie.get('Year'))

        # ---------- MODERN CARD ONTWERP ----------
        st.markdown("---")
        
        m_type = movie.get('Type', 'movie').capitalize()
        m_year = movie.get('Year', '?')
        m_runtime = movie.get('Runtime', 'Onbekend')
        m_genre = movie.get('Genre', 'Onbekend')
        m_nudity = get_sex_nudity_rating(chosen_id)
        
        with st.container(border=True):
            st.subheader(f"🍿 {movie.get('Title', 'Onbekende titel')}")
            
            # Badges-balk
            st.markdown(
                f"` {m_type} ` | ` 📅 {m_year} ` | ` ⏳ {m_runtime} ` | ` 🎭 {m_genre} ` | ` 🔞 Nudity: {m_nudity} `"
            )
            st.write("") 
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                poster = movie.get('Poster')
                if poster and poster != "N/A":
                    # GEFIXT: Gebruik de universele parameter die overal werkt
                    st.image(poster, use_column_width=True)
                else:
                    st.warning("Geen poster beschikbaar")
                    
            with col2:
                score_imdb = movie.get('imdbRating', 'N/A')
                score_rt = extract_rotten_tomatoes_score(movie)
                st.markdown(f"**⭐ IMDb:** `{score_imdb}/10` &nbsp;&nbsp;&nbsp;&nbsp; **🍅 Rotten Tomatoes:** `{score_rt}`")
                
                st.markdown(f"**🎬 Regisseur:** {movie.get('Director', 'Onbekend')}")
                
                cast = movie.get('Actors', 'Onbekend')
                if cast and cast != "N/A":
                    st.markdown(f"**🌟 Cast:** {cast}")
                
                st.markdown("**📖 Verhaal:**")
                st.write(movie.get('Plot', 'Geen beschrijving beschikbaar'))
                
                rt_query = f"{movie.get('Title', '')} {movie.get('Year', '')}"
                rt_url = f"https://www.rottentomatoes.com/search?search={requests.utils.quote(rt_query)}"
                
                st.markdown(
                    f"[🔗 Open op IMDb](https://www.imdb.com/title/{chosen_id}/) &nbsp;|&nbsp; [🔗 Open op Rotten Tomatoes]({rt_url})"
                )

        if trailer_url:
            st.write("")
            st.markdown("**📺 Officiële Trailer:**")
            st.video(trailer_url)
        else:
            st.warning("Geen trailer gevonden")

    except Exception as e:
        st.error(f"❌ Fout bij verwerken bestand: {str(e)}")