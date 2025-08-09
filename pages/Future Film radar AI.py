import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time

# Je TMDB config
tmdb_api_key = "98064dd9e851df83fdc6709c1e098107"

st.set_page_config(page_title="AI Radar zonder AI - Letterboxd + TMDB", layout="wide")
st.title("🎯 Future Film Radar – Zonder AI, met Letterboxd + TMDB")

# Sidebar filters (jaar + genre)
current_year = datetime.now().year
year = st.sidebar.selectbox("Selecteer een jaar", list(range(current_year, 2031)))

genre_mapping = {
    "Alles": None,
    "Actie": 28,
    "Avontuur": 12,
    "Animatie": 16,
    "Arthouse": 10749,
    "Biografie": 36,
    "Documentaire": 99,
    "Drama": 18,
    "Erotisch": 10749,
    "Fantasy": 14,
    "Historisch": 36,
    "Horror": 27,
    "Komedie": 35,
    "Misdaad": 80,
    "Mysterie": 9648,
    "Oorlog": 10752,
    "Romantiek": 10749,
    "Sciencefiction": 878,
    "Thriller": 53,
    "Western": 37
}
genre_name = st.sidebar.selectbox("Kies een genre", list(genre_mapping.keys()))
selected_genre_id = genre_mapping[genre_name]

only_future = st.sidebar.toggle("Toon enkel toekomstige releases", value=True)

# --- Letterboxd scraper functie ---
def scrape_letterboxd_popular(year, max_films=50):
    """
    Haal populaire films van Letterboxd voor een bepaald jaar.
    Scraped titel + link naar film pagina.
    """
    films = []
    page = 1
    base_url = f"https://letterboxd.com/films/popular/year/{year}/page/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
    }
    
    while len(films) < max_films:
        url = base_url + str(page) + "/"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            st.warning(f"Kon Letterboxd pagina niet laden: {url}")
            break
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Films staan in <div class="film-poster ...">, titel in data-film-name attr of alt img
        posters = soup.select("div.film-poster")
        if not posters:
            break
        
        for p in posters:
            if len(films) >= max_films:
                break
            title = p.get("data-film-name")
            if not title:
                # fallback: alt van img
                img = p.find("img")
                title = img["alt"] if img and img.has_attr("alt") else None
            
            if title:
                films.append(title)
        
        page += 1
        time.sleep(1)  # beleefd wachten
    
    return films

# --- TMDB zoekfunctie ---
def search_tmdb_movie(title):
    """
    Zoek een film op TMDB via titel, haal belangrijkste info
    """
    url = "https://api.themoviedb.org/3/search/movie"
    params = {
        "api_key": tmdb_api_key,
        "query": title,
        "language": "en-US",
        "page": 1,
        "include_adult": False
    }
    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        return None
    data = resp.json()
    results = data.get("results", [])
    if not results:
        return None
    
    # Kies de beste match (eerste resultaat)
    movie = results[0]
    return {
        "title": movie.get("title"),
        "release_date": movie.get("release_date"),
        "overview": movie.get("overview"),
        "poster": f"https://image.tmdb.org/t/p/w300{movie.get('poster_path')}" if movie.get("poster_path") else None,
        "genre_ids": movie.get("genre_ids", [])
    }

# --- Genre filter functie ---
def filter_by_genre(movies, genre_id):
    if genre_id is None:
        return movies
    return [m for m in movies if genre_id in m.get("genre_ids", [])]

# --- Main execution ---
if st.button("Laad populaire films van Letterboxd + TMDB data"):
    st.info(f"Laden van populaire films van Letterboxd uit {year}...")
    films = scrape_letterboxd_popular(year)
    st.success(f"{len(films)} films gevonden op Letterboxd, zoeken in TMDB...")

    tmdb_movies = []
    progress_bar = st.progress(0)
    for i, title in enumerate(films):
        movie_data = search_tmdb_movie(title)
        if movie_data:
            tmdb_movies.append(movie_data)
        progress_bar.progress((i+1) / len(films))
        time.sleep(0.25)  # niet te snel ivm API limiet
    
    # Filter op genre
    filtered = filter_by_genre(tmdb_movies, selected_genre_id)
    
    # Filter op toekomst
    if only_future:
        today = datetime.now().date().isoformat()
        filtered = [m for m in filtered if m.get("release_date") and m["release_date"] > today]
    
    if not filtered:
        st.warning("Geen films gevonden die aan de criteria voldoen.")
    else:
        st.subheader(f"🎬 Populaire films van Letterboxd voor {year} ({genre_name})")
        cols = st.columns(2)
        for i, film in enumerate(filtered):
            with cols[i % 2]:
                st.markdown(f"### {film['title']} ({film.get('release_date', 'Onbekend')})")
                if film["poster"]:
                    st.image(film["poster"], width=150)
                st.markdown(f"**Plot:** {film.get('overview', 'Geen beschrijving beschikbaar')}")
                st.divider()
