import streamlit as st
import requests
import random
from bs4 import BeautifulSoup

OMDB_API_KEY = "672ca221"  # Vervang eventueel met je eigen key

def get_movie_data(imdb_id):
    url = f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return {}

def get_poster(imdb_id):
    try:
        url = f"https://www.imdb.com/title/{imdb_id}/"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        meta = soup.find("meta", property="og:image")
        return meta["content"] if meta else None
    except:
        return None

def find_trailer_on_youtube(title, year):
    query = f"{title} {year} trailer"
    search_url = f"https://www.youtube.com/results?search_query={requests.utils.quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(search_url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    for link in soup.find_all("a"):
        href = link.get("href", "")
        if "/watch?v=" in href:
            return f"https://www.youtube.com{href}"
    return None

st.set_page_config(page_title="🎞️ IMDb Picker via Upload", layout="centered")
st.title("🎬 IMDb Random Picker (via upload)")
st.markdown("Upload een bestand (.txt of .csv) met IMDb ID’s (bv. `tt0111161`)")

uploaded_file = st.file_uploader("📤 Upload je lijst", type=["txt", "csv"])

if uploaded_file:
    imdb_ids = [line.strip() for line in uploaded_file.readlines()]
    imdb_ids = [id.decode("utf-8") if isinstance(id, bytes) else id for id in imdb_ids]
    imdb_ids = [id for id in imdb_ids if id.startswith("tt")]

    if not imdb_ids:
        st.warning("Geen geldige IMDb ID’s gevonden.")
    elif st.button("🎲 Kies een willekeurige titel"):
        chosen_id = random.choice(imdb_ids)
        movie_data = get_movie_data(chosen_id)
        poster_url = get_poster(chosen_id)
        trailer_url = find_trailer_on_youtube(movie_data.get("Title", ""), movie_data.get("Year", ""))

        st.subheader(f"{movie_data.get('Title')} ({movie_data.get('Year')})")
        st.markdown(f"⭐ IMDb Rating: **{movie_data.get('imdbRating', 'N/A')}**")
        st.markdown(f"[🔗 IMDb Link](https://www.imdb.com/title/{chosen_id}/)")

        if trailer_url:
            st.markdown(f"[🎥 Bekijk trailer]({trailer_url})")

        if poster_url:
            st.image(poster_url, width=300)
