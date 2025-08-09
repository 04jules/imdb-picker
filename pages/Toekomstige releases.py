import os
import streamlit as st
import requests
from datetime import datetime

# Streamlit config
st.set_page_config(page_title="🎥 Future Film Radar Pro", layout="wide")
st.title("🎥 Future Film Radar Pro")
st.markdown("De meest complete filmverkenner voor toekomstige releases")

# 🔑 API Keys uit Environment Variables
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
if not TMDB_API_KEY:
    st.error("❌ TMDB_API_KEY ontbreekt in de environment variables!")
    st.stop()

# --------- API FUNCTIES ---------
@st.cache_data(ttl=3600)
def fetch_movies_for_year(year, max_pages=5):
    """Haalt films op uit TMDB voor een specifiek jaar."""
    all_movies = []
    base_url = "https://api.themoviedb.org/3/discover/movie"
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    for page in range(1, max_pages + 1):
        params = {
            "api_key": TMDB_API_KEY,
            "language": "nl-NL",
            "sort_by": "popularity.desc",
            "include_adult": False,
            "primary_release_date.gte": start_date,
            "primary_release_date.lte": end_date,
            "page": page,
        }
        try:
            resp = requests.get(base_url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                break
            all_movies.extend(results)
            if page >= data.get("total_pages", 0):
                break
        except Exception as e:
            st.error(f"Fout bij ophalen films: {e}")
            break
    return all_movies

@st.cache_data(ttl=3600)
def get_movie_details(movie_id):
    """Haalt details op van een specifieke film."""
    url = f"https://api.themoviedb.org/3/movie/{movie_id}"
    params = {
        "api_key": TMDB_API_KEY,
        "language": "nl-NL",
        "append_to_response": "credits",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # Fallback naar Engels als geen NL beschrijving
        if not data.get("overview"):
            params["language"] = "en-US"
            resp_en = requests.get(url, params=params, timeout=5)
            if resp_en.ok:
                data_en = resp_en.json()
                data["overview"] = data_en.get("overview", "Geen beschrijving beschikbaar")
        return data
    except Exception:
        return None

# --------- HELPER FUNCTIES ---------
def format_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return "Onbekend"

def get_director(details):
    if not details or "credits" not in details:
        return "Onbekend"
    for person in details["credits"].get("crew", []):
        if person.get("job") == "Director":
            return person.get("name", "Onbekend")
    return "Onbekend"

def get_cast(details, max_cast=4):
    if not details or "credits" not in details:
        return []
    cast = details["credits"].get("cast", [])
    return [
        (actor["name"], f"https://image.tmdb.org/t/p/w185{actor['profile_path']}" if actor.get("profile_path") else None)
        for actor in cast[:max_cast]
    ]

def display_movie(movie, details):
    with st.container():
        st.markdown("---")
        col1, col2 = st.columns([1, 3])
        with col1:
            poster = movie.get("poster_path")
            if poster:
                st.image(f"https://image.tmdb.org/t/p/w500{poster}", use_container_width=True)
            else:
                st.warning("Geen poster beschikbaar")
        with col2:
            title_col, logo_col = st.columns([4, 1])
            with title_col:
                st.subheader(details.get("title", "Onbekende titel"))
            with logo_col:
                imdb_id = details.get("imdb_id", "")
                tmdb_id = str(movie.get("id", ""))
                st.markdown(f"""
                <div style="display:flex; justify-content:flex-end; gap:10px;">
                    <a href="https://www.imdb.com/title/{imdb_id}" target="_blank">
                        <img src="https://upload.wikimedia.org/wikipedia/commons/6/69/IMDB_Logo_2016.svg" width="40">
                    </a>
                    <a href="https://www.themoviedb.org/movie/{tmdb_id}" target="_blank">
                        <img src="https://upload.wikimedia.org/wikipedia/commons/8/89/Tmdb.new.logo.svg" width="40">
                    </a>
                </div>
                """, unsafe_allow_html=True)
            st.markdown(f"**🎬 Regisseur:** {get_director(details)}")
            st.markdown(f"**📅 Release datum:** {format_date(movie.get('release_date',''))}")
            runtime = details.get("runtime")
            st.markdown(f"**⏱️ Looptijd:** {runtime} minuten" if runtime else "**⏱️ Looptijd:** Onbekend")
            st.markdown(f"**⭐ Score:** {details.get('vote_average', 'N/A')}")
            cast = get_cast(details)
            if cast:
                st.markdown("**🌟 Hoofdrollen:**")
                cols = st.columns(min(4, len(cast)))
                for idx, (actor_name, actor_img) in enumerate(cast):
                    with cols[idx % 4]:
                        if actor_img:
                            st.image(actor_img, width=80, caption=actor_name)
                        else:
                            st.markdown(f"- {actor_name}")
            st.markdown(f"**📖 Verhaal:**  \n{details.get('overview', 'Geen beschrijving beschikbaar')}")

# --------- MAIN ---------
def main():
    st.sidebar.header("Filters")
    current_year = datetime.now().year
    years = [str(y) for y in range(current_year, current_year + 5)]
    selected_year = st.sidebar.selectbox("Jaar", years, index=0)

    genres = ["Alles", "Blockbuster", "Arthouse", "Erotisch", "Experimenteel"]
    selected_genre = st.sidebar.selectbox("Genre", genres)

    show_released = st.sidebar.checkbox("Toon al uitgebrachte films", value=False)

    with st.spinner("Films laden..."):
        movies = fetch_movies_for_year(int(selected_year))

    today = datetime.now().date()
    filtered_movies = []
    
    genre_map = {
        "Blockbuster": ["Actie", "Avontuur", "Science Fiction", "Fantasy", "Action", "Adventure", "Sci-Fi", "Fantasy"],
        "Arthouse": ["Drama", "Art House", "Independent"],
        "Erotisch": ["Romance", "Erotic"],
        "Experimenteel": ["Experimental", "Avant Garde"]
    }

    for movie in movies:
        release_date_str = movie.get("release_date")
        if not release_date_str:
            continue
        try:
            release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
        except Exception:
            continue

        # Filter released films
        if not show_released and release_date < today:
            continue

        details = get_movie_details(movie["id"])
        if not details:
            continue

        if selected_genre != "Alles":
            genre_names = [g["name"] for g in details.get("genres", [])]
            allowed_genres = genre_map.get(selected_genre, [])
            if not any(g in allowed_genres for g in genre_names):
                continue

        filtered_movies.append((movie, details))

    # Sorteren op release_date
    filtered_movies.sort(key=lambda x: x[0].get("release_date") or "")

    if not filtered_movies:
        st.warning("Geen films gevonden met deze filters. Probeer een ander jaar of genre.")
    else:
        st.success(f"Gevonden: {len(filtered_movies)} films voor {selected_year}")
        for movie, details in filtered_movies:
            display_movie(movie, details)

if __name__ == "__main__":
    main()
