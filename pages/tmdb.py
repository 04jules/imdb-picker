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

# ------------------------------
# API Keys
# ------------------------------
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")  # enkel nodig voor Rotten Tomatoes

if not TMDB_API_KEY:
    st.error("❌ Geen TMDb API key gevonden. Stel deze in als environment variable.")
    st.stop()

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
# TMDb: Zoek TMDb ID op basis van IMDb ID
# ------------------------------
@st.cache_data(show_spinner=True, ttl=3600)
def get_tmdb_data_from_imdb(imdb_id):
    try:
        # Zoek TMDb movie ID via IMDb ID
        url = f"https://api.themoviedb.org/3/find/{imdb_id}"
        params = {
            "api_key": TMDB_API_KEY,
            "external_source": "imdb_id",
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        # Movie of serie
        if data.get("movie_results"):
            movie = data["movie_results"][0]
            movie_type = "movie"
        elif data.get("tv_results"):
            movie = data["tv_results"][0]
            movie_type = "series"
        else:
            return {}

        # Haal extra details via movie/serie ID
        tmdb_id = movie["id"]
        details_url = f"https://api.themoviedb.org/3/{movie_type}/{tmdb_id}"
        params = {"api_key": TMDB_API_KEY, "append_to_response": "videos,external_ids,credits"}
        r2 = requests.get(details_url, params=params, timeout=10)
        r2.raise_for_status()
        details = r2.json()

        # Haal regisseur en cast op
        director = "Onbekend"
        cast = "Onbekend"
        
        if movie_type == "movie":
            # Voor films: regisseur zoeken in crew
            crew = details.get("credits", {}).get("crew", [])
            directors = [person for person in crew if person.get("job") == "Director"]
            if directors:
                director = directors[0].get("name", "Onbekend")
            
            # Cast voor films
            cast_members = details.get("credits", {}).get("cast", [])[:5]  # Top 5 acteurs
            if cast_members:
                cast = ", ".join([actor.get("name", "") for actor in cast_members if actor.get("name")])
        
        else:  # series
            # Voor series: creator zoeken
            creators = details.get("created_by", [])
            if creators:
                director = creators[0].get("name", "Onbekend")
            
            # Cast voor series
            cast_members = details.get("credits", {}).get("cast", [])[:5]  # Top 5 acteurs
            if cast_members:
                cast = ", ".join([actor.get("name", "") for actor in cast_members if actor.get("name")])

        result = {
            "imdb_id": imdb_id,
            "tmdb_id": tmdb_id,
            "type": movie_type,
            "title": movie.get("title") or movie.get("name"),
            "year": (movie.get("release_date") or movie.get("first_air_date") or "")[:4],
            "runtime": details.get("runtime") or (details.get("episode_run_time", [0])[0] if details.get("episode_run_time") else 0),
            "genres": ", ".join([g["name"] for g in details.get("genres", [])]),
            "overview": movie.get("overview") or details.get("overview") or "Geen beschrijving",
            "poster": f"https://image.tmdb.org/t/p/w300{movie['poster_path']}" if movie.get("poster_path") else None,
            "rating_tmdb": details.get("vote_average", "N/A"),
            "director": director,
            "cast": cast,
            "rt_score": None,  # vullen via OMDb als key beschikbaar
            "videos": details.get("videos", {}).get("results", [])
        }

        # Rotten Tomatoes via OMDb
        if OMDB_API_KEY:
            omdb_url = f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}"
            r3 = requests.get(omdb_url, timeout=10)
            if r3.status_code == 200:
                omdb_data = r3.json()
                for rate in omdb_data.get("Ratings", []):
                    if rate.get("Source") == "Rotten Tomatoes":
                        result["rt_score"] = rate.get("Value")
                        break

        return result
    except Exception as e:
        print(f"Error getting TMDB data for {imdb_id}: {e}")
        return {}

# ------------------------------
# 🎥 Find YouTube trailer (fallback)
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

# ------------------------------
# 🔞 IMDb Parental Guide: Sex & Nudity
# ------------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def get_sex_nudity_rating(imdb_id):
    try:
        url = f"https://www.imdb.com/title/{imdb_id}/parentalguide"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept-Language": "en-US,en;q=0.9"
        }
        r = requests.get(url, headers=headers, timeout=12)
        r.raise_for_status()
        html = r.text

        patterns = [
            r'data-testid="advisory-severity-item-SEX_AND_NUDITY"[^>]*>\s*<span[^>]*>(Mild|Moderate|Severe|None)</span',
            r'<h4>Sex & Nudity</h4>\s*<div[^>]*>\s*([^<]+)\s*</div',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                rating = match.group(1).strip().capitalize()
                if rating in ['Mild', 'Moderate', 'Severe', 'None']:
                    return rating
        return "Onbekend"
    except:
        return "Onbekend"

# ------------------------------
# 🚀 UI
# ------------------------------
st.title("🎬 IMDb Random Picker (TMDb versie: voorlopig blijft de omdb versie de primaire versie)")
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

        # ---------- TMDb data ophalen ----------
        rebuild = False
        if "all_data" not in st.session_state:
            rebuild = True
        if rebuild:
            st.session_state.all_data = []
            count = len(imdb_ids)
            with st.spinner("Titels ophalen via TMDb..."):
                progress = st.progress(0)
                for i, imdb_id in enumerate(imdb_ids):
                    data = get_tmdb_data_from_imdb(imdb_id)
                    if data:
                        st.session_state.all_data.append(data)
                    progress.progress((i + 1) / count)
                progress.empty()

        if not st.session_state.all_data:
            st.warning("⚠️ Geen titels gevonden via TMDb.")
            st.stop()

        # ---------- Random selectie ----------
        if "available_indices" not in st.session_state:
            st.session_state.available_indices = list(range(len(st.session_state.all_data)))
            random.shuffle(st.session_state.available_indices)

        if "last_selected_idx" not in st.session_state:
            st.session_state.last_selected_idx = st.session_state.available_indices.pop()

        if st.button("🔁 Nieuwe selectie", type="primary"):
            if st.session_state.available_indices:
                st.session_state.last_selected_idx = st.session_state.available_indices.pop()
            else:
                st.session_state.available_indices = list(range(len(st.session_state.all_data)))
                random.shuffle(st.session_state.available_indices)
                st.session_state.last_selected_idx = st.session_state.available_indices.pop()

        chosen_movie = st.session_state.all_data[st.session_state.last_selected_idx]

        # Poster / info
        col1, col2 = st.columns([1,2])
        with col1:
            if chosen_movie.get("poster"):
                st.image(chosen_movie["poster"], width=200)
            else:
                st.warning("Geen poster beschikbaar")
        with col2:
            st.subheader(f"{chosen_movie['title']} ({chosen_movie['year']})")
            st.markdown(f"**🎞️ Type:** {chosen_movie['type'].capitalize()}")
            st.markdown(f"**🎬 Regisseur:** {chosen_movie.get('director','Onbekend')}")
            
            # Cast als lijst weergeven
            if chosen_movie.get('cast') and chosen_movie['cast'] != "Onbekend":
                st.markdown("**🌟 Hoofdrolspelers:**")
                for actor in chosen_movie['cast'].split(', '):
                    st.markdown(f"- {actor}")
            else:
                st.markdown("**🌟 Hoofdrolspelers:** Onbekend")
                
            st.markdown(f"**⭐ TMDb Rating:** {chosen_movie.get('rating_tmdb','N/A')}")
            st.markdown(f"**🍅 Rotten Tomatoes:** {chosen_movie.get('rt_score','N/A')}")
            st.markdown(f"**⏳ Looptijd:** {chosen_movie.get('runtime','Onbekend')} min")
            st.markdown(f"**🎭 Genre:** {chosen_movie.get('genres','Onbekend')}")
            sex_rating = get_sex_nudity_rating(chosen_movie['imdb_id'])
            st.markdown(f"**🔞 Sex & Nudity:** {sex_rating}")

            # Links
            st.markdown(f"[⭐ IMDb](https://www.imdb.com/title/{chosen_movie['imdb_id']}/)")
            rt_query = f"{chosen_movie['title']} {chosen_movie['year']}"
            rt_url = f"https://www.rottentomatoes.com/search?search={requests.utils.quote(rt_query)}"
            st.markdown(f"[🍅 Rotten Tomatoes]({rt_url})")

            # Trailer: eerst TMDb video, fallback YouTube
            trailer_url = None
            for video in chosen_movie.get("videos", []):
                if video.get("type") == "Trailer" and video.get("site") == "YouTube":
                    trailer_url = f"https://www.youtube.com/watch?v={video['key']}"
                    break
            if not trailer_url:
                trailer_url = find_youtube_trailer(chosen_movie['title'], chosen_movie['year'])
            if trailer_url:
                st.video(trailer_url)
            else:
                st.warning("Geen trailer gevonden")

            st.markdown(f"**📖 Verhaal:**  \n{chosen_movie['overview']}")

    except Exception as e:
        st.error(f"❌ Fout bij verwerken bestand: {str(e)}")