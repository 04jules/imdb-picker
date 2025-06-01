import streamlit as st
import requests
import random
import pandas as pd
from bs4 import BeautifulSoup
import re

# Vervang met je eigen OMDb API key indien nodig
OMDB_API_KEY = "672ca221"

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
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        meta = soup.find("meta", property="og:image")
        return meta["content"] if meta else None
    except:
        return None

def find_trailer_on_youtube(title, year):
    query = f"{title} {year} trailer"
    search_url = f"https://www.youtube.com/results?search_query={requests.utils.quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(search_url, headers=headers, timeout=10)
    soup = BeautifulSoup(res.text, "html.parser")
    for link in soup.find_all("a"):
        href = link.get("href", "")
        if "/watch?v=" in href:
            return f"https://www.youtube.com{href}"
    return None

# Streamlit UI configuratie
st.set_page_config(page_title="🎞️ IMDb Picker via Upload", layout="centered")
st.title("🎬 IMDb Random Picker (via CSV-upload)")
st.markdown("Upload een IMDb-export CSV-bestand (bijvoorbeeld `watchlist.csv`) of een andere CSV waarin IMDb ID’s `tt1234567` voorkomen.")

uploaded_file = st.file_uploader("📤 Upload je CSV-bestand", type=["csv"])

if uploaded_file:
    try:
        # Lees de CSV in een DataFrame
        df = pd.read_csv(uploaded_file)
        # Zoek naar IMDb ID's in alle kolommen
        imdb_ids = set()
        pattern = re.compile(r'^tt\\d+$')
        for col in df.columns:
            for val in df[col].astype(str).str.strip():
                if pattern.match(val):
                    imdb_ids.add(val)
        imdb_ids = list(imdb_ids)
    except Exception as e:
        st.error(f"Fout bij inlezen van bestand: {e}")
        imdb_ids = []

    if not imdb_ids:
        st.warning("Geen geldige IMDb ID’s gevonden in je upload. Zorg dat er strings als 'tt0123456' in de CSV staan.")
    elif st.button("🎲 Kies een willekeurige titel"):
        chosen_id = random.choice(imdb_ids)
        movie_data = get_movie_data(chosen_id)
        title = movie_data.get("Title", "Onbekende titel")
        year = movie_data.get("Year", "")
        rating = movie_data.get("imdbRating", "N/A")
        poster_url = get_poster(chosen_id)
        trailer_url = find_trailer_on_youtube(title, year)

        st.subheader(f"{title} ({year})")
        st.markdown(f"⭐ IMDb Rating: **{rating}**")
        st.markdown(f"[🔗 IMDb Link](https://www.imdb.com/title/{chosen_id}/)")

        if trailer_url:
            st.markdown(f"[🎥 Bekijk trailer]({trailer_url})")

        if poster_url:
            st.image(poster_url, width=300)
