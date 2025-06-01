import streamlit as st
import random
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# Functie om titels op te halen
@st.cache_data(show_spinner="Titels worden opgehaald...")
def fetch_imdb_titles_selenium(url):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)
    
    try:
        items = driver.find_elements(By.CSS_SELECTOR, "li.ipc-metadata-list-summary-item")
        titles = []
        for item in items:
            try:
                title_element = item.find_element(By.CSS_SELECTOR, "a.ipc-title-link-wrapper")
                title = title_element.text
                href = title_element.get_attribute("href")
                imdb_id = href.split('/title/')[1].split('/')[0]
                titles.append({'title': title, 'id': imdb_id})
            except:
                continue
        return titles
    finally:
        driver.quit()

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

# Rating ophalen
def get_imdb_rating(imdb_id):
    api_key = "672ca221"  # Let op: vervang met eigen key als nodig
    url = f"http://www.omdbapi.com/?i={imdb_id}&apikey={api_key}"
    r = requests.get(url).json()
    return r.get("imdbRating", "N/A")

# Streamlit interface
st.set_page_config(page_title="IMDb Picker", layout="centered")

st.title("🎬 IMDb Random Picker")
imdb_url = st.text_input("Plak hier je IMDb watchlist of lijst-URL:", "https://www.imdb.com/user/ur163756834/watchlist")

if st.button("🎲 Kies een willekeurige titel"):
    with st.spinner("Laden..."):
        titles = fetch_imdb_titles_selenium(imdb_url)
    
    if not titles:
        st.error("Geen titels gevonden!")
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