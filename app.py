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
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Regisseur ophalen
        director = "Onbekend"
        director_section = soup.find('li', {'data-testid': 'title-pc-principal-credit'})
        if director_section:
            director = director_section.get_text(strip=True).replace('Director', '')
        
        # Top cast ophalen (eerste 5 acteurs)
        cast = []
        cast_section = soup.find('div', {'data-testid': 'title-cast'})
        if cast_section:
            cast_items = cast_section.find_all('a', {'data-testid': 'title-cast-item__actor'}, limit=5)
            cast = [item.get_text(strip=True) for item in cast_items]
        
        return {
            'director': director,
            'cast': cast if cast else ["Geen cast informatie beschikbaar"]
        }
    except Exception:
        return {
            'director': "Kon regisseur niet ophalen",
            'cast': ["Kon cast niet ophalen"]
        }

@st.cache_data(show_spinner=False, ttl=3600)
def get_poster_url(imdb_id):
    """Haal poster URL op van IMDb"""
    try:
        url = f"https://www.imdb.com/title/{imdb_id}/"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        meta = soup.find("meta", property="og:image")
        return meta["content"] if meta else None
    except Exception:
        return None

@st.cache_data(show_spinner=False, ttl=3600)
def find_youtube_trailer(title, year):
    """Zoek YouTube trailer URL"""
    try:
        query = f"{title} {year} official trailer"
        search_url = f"https://www.youtube.com/results?search_query={requests.utils.quote(query)}"
        
        response = requests.get(search_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Moderne YouTube resultaten
        scripts = soup.find_all("script")
        for script in scripts:
            if 'ytInitialData' in script.text:
                data = json.loads(script.text.split('ytInitialData = ')[1].split(';')[0])
                jsonpath_expr = parse('$..videoRenderer[0].videoId')
                matches = [match.value for match in jsonpath_expr.find(data)]
                if matches:
                    return f"https://youtube.com/watch?v={matches[0]}"
        
        # Fallback voor oudere YouTube versies
        for link in soup.find_all("a", href=True):
            if "/watch?v=" in link["href"]:
                return f"https://youtube.com{link['href']}"
                
        return None
    except Exception:
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
                    st.markdown(f"**🎬 Regisseur:** {imdb_details['director']}")
                    
                    # Toon top cast
                    st.markdown("**🌟 Hoofdrolspelers:**")
                    for actor in imdb_details['cast']:
                        st.markdown(f"- {actor}")
                    
                    st.markdown(f"**⭐ IMDb Rating:** {movie.get('imdbRating', 'N/A')}")
                    st.markdown(f"**⏳ Looptijd:** {movie.get('Runtime', 'Onbekend')}")
                    st.markdown(f"**🎭 Genre:** {movie.get('Genre', 'Onbekend')}")
                    
                    # IMDb link
                    imdb_url = f"https://www.imdb.com/title/{chosen_id}/"
                    st.markdown(f"[🔗 IMDb pagina]({imdb_url})")
                    
                    # YouTube trailer
                    trailer_url = find_youtube_trailer(movie['Title'], movie['Year'])
                    if trailer_url:
                        st.markdown(f"[🎥 Bekijk trailer]({trailer_url})")
                    
                    # Plot
                    st.markdown(f"**📖 Verhaal:**  \n{movie.get('Plot', 'Geen beschrijving beschikbaar')}")
    
    except Exception as e:
        st.error(f"❌ Fout bij verwerken bestand: {str(e)}")