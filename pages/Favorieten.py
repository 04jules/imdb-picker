# pages/Favorieten.py
import streamlit as st

st.title("📂 Mijn favorieten")

if "favorites" not in st.session_state or not st.session_state.favorites:
    st.info("Je hebt nog geen favorieten toegevoegd.")
else:
    for imdb_id, movie in st.session_state.favorites:
        st.markdown(f"### 🎬 {movie.get('Title')} ({movie.get('Year')})")
        st.markdown(f"- ⭐ IMDb Rating: {movie.get('imdbRating', 'N/A')}")
        st.markdown(f"- 🎭 Genre: {movie.get('Genre', 'Onbekend')}")
        st.markdown(f"[🔗 IMDb link](https://www.imdb.com/title/{imdb_id}/)")
        st.markdown("---")
