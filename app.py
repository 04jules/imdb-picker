import os
import streamlit as st
import pandas as pd
import requests
import random
import re
import time
from bs4 import BeautifulSoup
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

def get_movie_data(imdb_id):
    try:
        url = f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()
        return data if data.get('Response') == 'True' else {}
    except:
        return {}

def get_imdb_details_and_poster(imdb_id):
    """Haalt regisseur, cast en poster in 1x op (sneller)."""
    try:
        url = f"https://www.imdb.com/title/{imdb_id}/"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        director = "Onbekend"
        director_section = soup.select_one('li[data-testid="title-pc-principal-credit"]')
        if director_section:
            director = director_section.get_text(strip=True).replace('Director', '').strip()

        cast = [item.get_text(strip=True) for item in soup.select('a[data-testid="title-cast-item__actor"]')[:5]]
        if not cast:
            cast = ["Geen cast informatie beschikbaar"]

        meta = soup.find("meta", property="og:image")
        poster_url = meta["content"] if meta else None

        return {"director": director, "cast": cast, "poster_url": poster_url}
    except:
        return {"director": "Onbekend", "cast": ["Geen info"], "poster_url": None}

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

# UI start
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

        st.success(f"✅ {len(imdb_ids)} IMDb ID's gevonden!")
        media_type = st.selectbox("📺 Wat wil je kijken?", ["Alles", "Alleen films", "Alleen series"])

        # Eerste keer laden: progress bar en data cachen
        if "all_data" not in st.session_state:
            st.session_state.all_data = []
            progress = st.progress(0)
            for i, imdb_id in enumerate(imdb_ids[:50]):
                movie_data = get_movie_data(imdb_id)
                if movie_data:
                    if (media_type == "Alleen films" and movie_data.get("Type") != "movie") or \
                       (media_type == "Alleen series" and movie_data.get("Type") != "series"):
                        continue
                    details = get_imdb_details_and_poster(imdb_id)
                    trailer = find_youtube_trailer(movie_data.get('Title'), movie_data.get('Year'))
                    st.session_state.all_data.append((imdb_id, movie_data, details, trailer))
                progress.progress((i+1) / min(len(imdb_ids[:50]), 50))
            progress.empty()

        if not st.session_state.all_data:
            st.warning("⚠️ Geen titels gevonden met dat type.")
            st.stop()

        if "last_selected" not in st.session_state:
            st.session_state.last_selected = random.choice(st.session_state.all_data)

        # Nieuwe selectie zonder opnieuw laden
        if st.button("🔁 Nieuwe selectie", type="primary"):
            available_choices = [x for x in st.session_state.all_data if x != st.session_state.last_selected]
            st.session_state.last_selected = random.choice(available_choices)

        if "favorites" not in st.session_state:
            st.session_state.favorites = []

        if st.session_state.last_selected:
            chosen_id, movie, imdb_details, trailer_url = st.session_state.last_selected

            col_title, col_button = st.columns([3, 1])
            with col_title:
                st.subheader(f"{movie.get('Title', 'Onbekende titel')} ({movie.get('Year', '?')})")
            with col_button:
                if st.button("❤️ Voeg toe aan favorieten"):
                    if chosen_id not in [fav[0] for fav in st.session_state.favorites]:
                        st.session_state.favorites.append((chosen_id, movie))

            col1, col2 = st.columns([1, 2])
            with col1:
                if imdb_details['poster_url']:
                    st.image(imdb_details['poster_url'], width=200)
                else:
                    st.warning("Geen poster beschikbaar")
            with col2:
                st.markdown(f"**🎞️ Type:** {movie.get('Type', 'Onbekend').capitalize()}")
                st.markdown(f"**🎬 Regisseur:** {imdb_details['director']}")
                st.markdown("**🌟 Hoofdrolspelers:**")
                for actor in imdb_details['cast']:
                    st.markdown(f"- {actor}")
                st.markdown(f"**⭐ IMDb Rating:** {movie.get('imdbRating', 'N/A')}")
                st.markdown(f"**⏳ Looptijd:** {movie.get('Runtime', 'Onbekend')}")
                st.markdown(f"**🎭 Genre:** {movie.get('Genre', 'Onbekend')}")
                st.markdown(f"[🔗 IMDb pagina](https://www.imdb.com/title/{chosen_id}/)")
                if trailer_url:
                    st.video(trailer_url)
                else:
                    st.warning("Geen trailer gevonden")
                st.markdown(f"**📖 Verhaal:**  \n{movie.get('Plot', 'Geen beschrijving beschikbaar')}")

    except Exception as e:
        st.error(f"❌ Fout bij verwerken bestand: {str(e)}")
