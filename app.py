import os
import streamlit as st
import pandas as pd
import requests
import random
import re
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

@st.cache_data(show_spinner=True, ttl=3600)
def get_movie_data(imdb_id):
    try:
        url = f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}&plot=full"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data if data.get('Response') == 'True' else {}
    except:
        return {}

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

def get_actor_image_url(name):
    # IMDb heeft geen officiële actor pics via API, maar fanpages wel.
    # Hier een gokje: https://www.imdb.com/name/nmXXXXXXX/  fotos worden geladen dynamisch.
    # Zonder API kunnen we alleen voor bekende actors geen foto ophalen via naam.
    # Als alternatief: gebruik een dummy placeholder of niets.
    # Voor nu return None, of als je actor foto's wilt via andere API, kan dit uitgebreid worden.
    return None

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

        rebuild = False
        if "all_data" not in st.session_state:
            rebuild = True
        elif st.session_state.get("last_media_type") != media_type:
            rebuild = True

        if rebuild:
            st.session_state.all_data = []
            st.session_state.last_media_type = media_type
            count = len(imdb_ids)
            with st.spinner("Titels ophalen en cachen... Dit kan even duren bij grote lijsten."):
                progress = st.progress(0)
                for i, imdb_id in enumerate(imdb_ids):
                    movie_data = get_movie_data(imdb_id)
                    if not movie_data:
                        progress.progress((i+1)/count)
                        continue
                    st.session_state.all_data.append((imdb_id, movie_data))
                    progress.progress((i+1)/count)
                progress.empty()

            if media_type == "Alleen films":
                st.session_state.all_data = [item for item in st.session_state.all_data if item[1].get("Type") == "movie"]
            elif media_type == "Alleen series":
                st.session_state.all_data = [item for item in st.session_state.all_data if item[1].get("Type") == "series"]

        if not st.session_state.all_data:
            st.warning("⚠️ Geen titels gevonden met dat type.")
            st.stop()

        if "last_selected_idx" not in st.session_state or st.session_state.last_selected_idx >= len(st.session_state.all_data):
            st.session_state.last_selected_idx = random.randrange(len(st.session_state.all_data))

        if st.button("🔁 Nieuwe selectie", type="primary"):
            total = len(st.session_state.all_data)
            if total == 1:
                st.info("Er is maar één titel beschikbaar — kan niet wisselen.")
            else:
                new_idx = random.randrange(total)
                tries = 0
                while new_idx == st.session_state.last_selected_idx and tries < 10:
                    new_idx = random.randrange(total)
                    tries += 1
                if new_idx == st.session_state.last_selected_idx:
                    new_idx = (st.session_state.last_selected_idx + 1) % total
                st.session_state.last_selected_idx = new_idx

        if "favorites" not in st.session_state:
            st.session_state.favorites = []

        chosen_id, movie = st.session_state.all_data[st.session_state.last_selected_idx]

        trailer_url = find_youtube_trailer(movie.get('Title'), movie.get('Year'))

        # Animatie fade-in simulatie: gebruikst een tijdelijke placeholder en dan vervanging.
        placeholder = st.empty()
        with placeholder.container():
            col_title, col_button = st.columns([3, 1])
            with col_title:
                st.subheader(f"{movie.get('Title', 'Onbekende titel')} ({movie.get('Year', '?')})")
            with col_button:
                if st.button("❤️ Voeg toe aan favorieten"):
                    if chosen_id not in [fav[0] for fav in st.session_state.favorites]:
                        st.session_state.favorites.append((chosen_id, movie))

            col1, col2 = st.columns([1, 2])
            with col1:
                poster = movie.get('Poster')
                if poster and poster != "N/A":
                    st.image(poster, width=200)
                else:
                    st.warning("Geen poster beschikbaar")
            with col2:
                st.markdown(f"**🎞️ Type:** {movie.get('Type', 'Onbekend').capitalize()}")
                st.markdown(f"**🎭 Genre:** {movie.get('Genre', 'Onbekend')}")
                st.markdown(f"**🎬 Regisseur:** {movie.get('Director', 'Onbekend')}")
                cast = movie.get('Actors', 'Geen cast informatie beschikbaar')
                if cast and cast != "N/A":
                    st.markdown("**🌟 Hoofdrolspelers:**")
                    actors = [a.strip() for a in cast.split(',')]
                    # Toon naam + dummy foto (voor nu geen echte foto, kan uitgebreid worden)
                    for actor in actors:
                        cols = st.columns([0.3, 2])
                        with cols[0]:
                            st.image("https://upload.wikimedia.org/wikipedia/commons/8/89/Portrait_Placeholder.png", width=40)
                        with cols[1]:
                            st.markdown(f"- {actor}")
                else:
                    st.markdown("**🌟 Hoofdrolspelers:** Geen cast informatie beschikbaar")
                st.markdown(f"**⭐ IMDb Rating:** {movie.get('imdbRating', 'N/A')}")
                st.markdown(f"**⏳ Looptijd:** {movie.get('Runtime', 'Onbekend')}")
                st.markdown(f"[🔗 IMDb pagina](https://www.imdb.com/title/{chosen_id}/)")
                if trailer_url:
                    st.video(trailer_url)
                else:
                    st.warning("Geen trailer gevonden")
                st.markdown(f"**📖 Verhaal:**  \n{movie.get('Plot', 'Geen beschrijving beschikbaar')}")

        # Simuleer fade effect met korte vertraging en opnieuw tonen (echt fade-in kan Streamlit niet, maar dit is een eenvoudige hint)
        import time
        placeholder.empty()
        time.sleep(0.1)
        placeholder.container()

    except Exception as e:
        st.error(f"❌ Fout bij verwerken bestand: {str(e)}")
