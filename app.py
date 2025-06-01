import random
import requests
from bs4 import BeautifulSoup
import streamlit as st

# Functie om titels en IMDb-IDs op te halen
@st.cache_data(show_spinner="Titels worden opgehaald...")
def fetch_imdb_titles_simple(imdb_list_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(imdb_list_url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    titles = []

    for item in soup.select('.lister-item'):
        header = item.select_one('.lister-item-header a')
        if header:
            title = header.text.strip()
            href = header['href']
            # IMDb ID extraheren uit de link, bv: /title/tt1234567/
            imdb_id = href.split('/')[2]
            titles.append({'title': title, 'id': imdb_id})

    return titles

# Poster ophalen
def get_poster(imdb_id):
    try:
        url = f"https://www.imdb.com/title/{imdb_id}/"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        meta = soup.find('meta', property='og:image')
        if meta and meta.get('content'):
            return meta['content']
    except:
        pass
    return None

# Rating ophalen via OMDb API
def get_imdb_rating(imdb_id):
    api_key = "672ca221"  # Vervang met je eigen API key indien nodig
    url = f"http://www.omdbapi.com/?i={imdb_id}&apikey={api_key}"
    try:
        r = requests.get(url, timeout=10).json()
        return r.get("imdbRating", "N/A")
    except:
        return "N/A"

# Streamlit UI
st.set_page_config(page_title="IMDb Picker", layout="centered")
st.title("🎬 IMDb Random Picker")

imdb_url = st.text_input("Plak hier je IMDb Watchlist of andere lijst-URL:")

if st.button("🎲 Kies een willekeurige titel"):
    with st.spinner("Lijst wordt opgehaald..."):
        titles = fetch_imdb_titles_simple(imdb_url)

    if not titles:
        st.error("Geen titels gevonden! Zorg dat je een publieke IMDb-lijst gebruikt.")
    else:
        choice = random.choice(titles)
        title = choice['title']
        imdb_id = choice['id']
        poster_url = get_poster(imdb_id)
        rating = get_imdb_rating(imdb_id)

        st.subheader(title)
        st.markdown(f"⭐ IMDb Rating: **{rating}**")
        st.markdown(f"[🔗 Bekijk op IMDb](https://www.imdb.com/title/{imdb_id}/)")

        if poster_url:
            st.image(poster_url, width=300)
