import streamlit as st
import pandas as pd
import requests
import random
import re
from bs4 import BeautifulSoup
import json
from jsonpath_ng import jsonpath, parse
from io import StringIO

# Configuratie
st.set_page_config(page_title="🎬 IMDb Random Picker", layout="centered")
OMDB_API_KEY = "672ca221"  # Vervang met je eigen key

# Functies
@st.cache_data(show_spinner=False)
def extract_imdb_ids(df):
    """Extraheer alle unieke IMDb ID's uit een DataFrame"""
    imdb_ids = set()
    pattern = re.compile(r'(tt\d{7,8})')  # Vindt tt gevolgd door 7-8 cijfers
    
    for col in df.columns:
        try:
            # Zoek in elke cel van elke kolom
            matches = df[col].astype(str).str.extractall(pattern)[0].unique()
            for match in matches:
                if pd.notna(match):
                    imdb_ids.add(match)
        except Exception as e:
            continue
            
    return list(imdb_ids)

@st.cache_data(show_spinner=False, ttl=3600)
def get_movie_data(imdb_id):
    """Haal filmdata op van OMDB API"""
    try:
        url = f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data if data.get('Response') == 'True' else {}
    except Exception:
        return {}

@st.cache_data(show_spinner=False, ttl=3600)
def get_imdb_details(imdb_id):
    """Haal extra details op van IMDb pagina"""
    try:
        url = f"https://www.imdb.com/title/{imdb_id}/"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Regisseur ophalen
        director = "Onbekend"
        director_section = soup.select_one('li[data-testid="title-pc-principal-credit"]:contains("Director")')
        if director_section:
            director = director_section.get_text(strip=True).replace('Director', '').strip()
        
        # Top cast ophalen (eerste 5 acteurs)
        cast = []
        cast_items = soup.select('a[data-testid="title-cast-item__actor"]')
        for item in cast_items[:5]:  # Beperk tot eerste 5
            actor = item.get_text(strip=True)
            if actor:
                cast.append(actor)
        
        return {
            'director': director,
            'cast': cast if cast else ["Geen cast informatie beschikbaar"]
        }
    except Exception as e:
        print(f"Fout bij ophalen IMDb details: {str(e)}")
        return {
            'director': "Kon regisseur niet ophalen",
            'cast': ["Kon cast niet ophalen"]
        }

@st.cache_data(show_spinner=False, ttl=3600)
def get_poster_url(imdb_id):
    """Haal poster URL op van IMDb"""
    try:
        url = f"https://www.imdb.com/title/{imdb_id}/"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        meta = soup.find("meta", property="og:image")
        return meta["content"] if meta else None
    except Exception as e:
        print(f"Fout bij ophalen poster: {str(e)}")
        return None

@st.cache_data(show_spinner=False, ttl=3600)
def find_youtube_trailer(title, year):
    """Zoek YouTube trailer URL met verbeterde methode"""
    try:
        query = f"{title} {year} official trailer site:youtube.com"
        search_url = f"https://www.youtube.com/results?search_query={requests.utils.quote(query)}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Eenvoudigere methode om YouTube video ID te vinden
        video_ids = re.findall(r'watch\?v=(\S{11})', response.text)
        if video_ids:
            return f"https://www.youtube.com/watch?v={video_ids[0]}"
        
        return None
    except Exception as e:
        print(f"Fout bij zoeken trailer: {str(e)}")
        return None

# UI
st.title("🎬 IMDb Random Picker")
st.markdown("""
Upload een CSV-bestand met IMDb ID's (zoals `tt1234567`).  
Werkt met IMDb watchlist exports of elke CSV met IMDb ID's.
""")

# Voorbeeld CSV
with st.expander("📋 Voorbeeld CSV-formaat"):
    st.code("""Const,Title,Year
tt0111161,The Shawshank Redemption,1994
tt0068646,The Godfather,1972
tt0071562,The Godfather Part II,1974""")

# Bestand upload
uploaded_file = st.file_uploader("📤 Upload CSV-bestand", type=["csv"])

if uploaded_file:
    try:
        # Lees CSV (probeer verschillende encodings)
        try:
            df = pd.read_csv(uploaded_file)
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            content = uploaded_file.read().decode('latin-1')
            df = pd.read_csv(StringIO(content))
        
        # Extraheer IMDb ID's
        with st.spinner("🔍 Zoek naar IMDb ID's..."):
            imdb_ids = extract_imdb_ids(df)
        
        if not imdb_ids:
            st.warning("⚠️ Geen IMDb ID's gevonden. Zorg dat je bestand IDs bevat zoals tt1234567")
            st.stop()
            
        st.success(f"✅ {len(imdb_ids)} IMDb ID's gevonden!")
        
        if st.button("🎲 Willekeurige film selecteren", type="primary"):
            with st.spinner("🎥 Filmgegevens ophalen..."):
                chosen_id = random.choice(imdb_ids)
                movie = get_movie_data(chosen_id)
                imdb_details = get_imdb_details(chosen_id)
                poster_url = get_poster_url(chosen_id)
                
                if not movie:
                    st.error("Kon filmgegevens niet ophalen van OMDB")
                    st.stop()
                
                # Toon resultaten
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    if poster_url:
                        st.image(poster_url, width=200)
                    else:
                        st.warning("Geen poster beschikbaar")
                
                with col2:
                    st.subheader(f"{movie.get('Title', 'Onbekende titel')} ({movie.get('Year', '?')})")
                    
                    # Regisseur
                    st.markdown(f"**🎬 Regisseur:** {imdb_details['director']}")
                    
                    # Cast
                    if imdb_details['cast']:
                        st.markdown("**🌟 Hoofdrolspelers:**")
                        for actor in imdb_details['cast']:
                            st.markdown(f"- {actor}")
                    
                    # Overige details
                    st.markdown(f"**⭐ IMDb Rating:** {movie.get('imdbRating', 'N/A')}")
                    st.markdown(f"**⏳ Looptijd:** {movie.get('Runtime', 'Onbekend')}")
                    st.markdown(f"**🎭 Genre:** {movie.get('Genre', 'Onbekend')}")
                    
                    # IMDb link
                    imdb_url = f"https://www.imdb.com/title/{chosen_id}/"
                    st.markdown(f"[🔗 IMDb pagina]({imdb_url})")
                    
                    # YouTube trailer
                    trailer_url = find_youtube_trailer(movie.get('Title'), movie.get('Year'))
                    if trailer_url:
                        st.video(trailer_url)
                    else:
                        st.warning("Geen trailer gevonden")
                    
                    # Plot
                    st.markdown(f"**📖 Verhaal:**  \n{movie.get('Plot', 'Geen beschrijving beschikbaar')}")
    
    except Exception as e:
        st.error(f"❌ Fout bij verwerken bestand: {str(e)}")