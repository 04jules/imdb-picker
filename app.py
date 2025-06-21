import streamlit as st
import pandas as pd
import requests
import random
import re
from bs4 import BeautifulSoup
from io import StringIO

# Configuratie
st.set_page_config(page_title="🎬 IMDb Random Picker", layout="centered")
OMDB_API_KEY = "672ca221"  # Vervang met je eigen key

# Functies
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

@st.cache_data(show_spinner=False, ttl=3600)
def get_movie_data(imdb_id):
    try:
        url = f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data if data.get('Response') == 'True' else {}
    except:
        return {}

def get_imdb_details(imdb_id):
    try:
        url = f"https://www.imdb.com/title/{imdb_id}/"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Regisseur
        director = "Onbekend"
        director_section = soup.select_one('li[data-testid="title-pc-principal-credit"]:-soup-contains("Director")')
        if director_section:
            director = director_section.get_text(strip=True).replace('Director', '').strip()
        
        # Cast
        cast = []
        cast_items = soup.select('a[data-testid="title-cast-item__actor"]')
        for item in cast_items[:5]:
            actor = item.get_text(strip=True)
            if actor:
                cast.append(actor)
        
        return {
            'director': director,
            'cast': cast if cast else ["Geen cast informatie beschikbaar"]
        }
    except:
        return {
            'director': "Kon regisseur niet ophalen",
            'cast': ["Kon cast niet ophalen"]
        }

def get_poster_url(imdb_id):
    try:
        url = f"https://www.imdb.com/title/{imdb_id}/"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        meta = soup.find("meta", property="og:image")
        return meta["content"] if meta else None
    except:
        return None

def find_youtube_trailer(title, year):
    try:
        query = f"{title} {year} official trailer site:youtube.com"
        search_url = f"https://www.youtube.com/results?search_query={requests.utils.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()
        video_ids = re.findall(r'watch\?v=(\S{11})', response.text)
        if video_ids:
            return f"https://www.youtube.com/watch?v={video_ids[0]}"
        return None
    except:
        return None

# UI
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
        
        with st.spinner("🔍 IMDb ID's worden gezocht..."):
            imdb_ids = extract_imdb_ids(df)
        
        if not imdb_ids:
            st.warning("⚠️ Geen IMDb ID's gevonden.")
            st.stop()
        st.success(f"✅ {len(imdb_ids)} IMDb ID's gevonden!")

        # Mediatype filter
        media_type = st.selectbox("📺 Wat wil je kijken?", ["Alles", "Alleen films", "Alleen series"])

        # Vooraf ophalen van OMDb-data
        with st.spinner("📦 Ophalen metadata van OMDb..."):
            all_data = []
            for imdb_id in imdb_ids:
                data = get_movie_data(imdb_id)
                if data:
                    all_data.append((imdb_id, data))

        # Filteren op type
        if media_type == "Alleen films":
            filtered = [(id_, d) for id_, d in all_data if d.get("Type") == "movie"]
        elif media_type == "Alleen series":
            filtered = [(id_, d) for id_, d in all_data if d.get("Type") == "series"]
        else:
            filtered = all_data

        if not filtered:
            st.warning("⚠️ Geen titels gevonden met dat type.")
            st.stop()

        # In-memory cache voor extra details
        if "details_cache" not in st.session_state:
            st.session_state.details_cache = {}

        if st.button("🎲 Willekeurige selectie", type="primary"):
            chosen_id, movie = random.choice(filtered)

            if chosen_id in st.session_state.details_cache:
                details = st.session_state.details_cache[chosen_id]
            else:
                imdb_details = get_imdb_details(chosen_id)
                poster_url = get_poster_url(chosen_id)
                trailer_url = find_youtube_trailer(movie.get('Title'), movie.get('Year'))
                details = {
                    "imdb_details": imdb_details,
                    "poster_url": poster_url,
                    "trailer_url": trailer_url
                }
                st.session_state.details_cache[chosen_id] = details

            imdb_details = details["imdb_details"]
            poster_url = details["poster_url"]
            trailer_url = details["trailer_url"]

            col1, col2 = st.columns([1, 2])
            with col1:
                if poster_url:
                    st.image(poster_url, width=200)
                else:
                    st.warning("Geen poster beschikbaar")

            with col2:
                st.subheader(f"{movie.get('Title', 'Onbekende titel')} ({movie.get('Year', '?')})")
                st.markdown(f"**🎞️ Type:** {movie.get('Type', 'Onbekend').capitalize()}")
                st.markdown(f"**🎬 Regisseur:** {imdb_details['director']}")
                st.markdown("**🌟 Hoofdrolspelers:**")
                for actor in imdb_details['cast']:
                    st.markdown(f"- {actor}")
                st.markdown(f"**⭐ IMDb Rating:** {movie.get('imdbRating', 'N/A')}")
                st.markdown(f"**⏳ Looptijd:** {movie.get('Runtime', 'Onbekend')}")
                st.markdown(f"**🎭 Genre:** {movie.get('Genre', 'Onbekend')}")
                imdb_url = f"https://www.imdb.com/title/{chosen_id}/"
                st.markdown(f"[🔗 IMDb pagina]({imdb_url})")
                if trailer_url:
                    st.video(trailer_url)
                else:
                    st.warning("Geen trailer gevonden")
                st.markdown(f"**📖 Verhaal:**  \n{movie.get('Plot', 'Geen beschrijving beschikbaar')}")

    except Exception as e:
        st.error(f"❌ Fout bij verwerken bestand: {str(e)}")
