

import streamlit as st
import pandas as pd
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import difflib
import urllib.parse

# ---------------- CONFIG ----------------
# OMDB_API_KEY = "2cb9d5c7"  # Replace with your OMDb API key

OMDB_API_KEY = st.secrets["OMDB_API_KEY"]

N_RECOMMEND = 5

st.set_page_config(page_title="Movie Recommender", layout="wide", page_icon="🎥")

# ---------------- STYLES ----------------
st.markdown("""
<style>
body {
    background-color: #0d0f1a;
    color: #ffffff;
}
.movie-card {
    background: linear-gradient(180deg, #1c1e2b, #11121a);
    border-radius: 15px;
    padding-top: 10px;
    text-align: center;
    box-shadow: 0px 6px 16px rgba(0,0,0,0.5);
    transition: transform 0.2s;
    min-width: 180px;
    max-width: 180px;
    display: inline-block;
}
.movie-card:hover {
    transform: scale(1.05);
}
.movie-title {
    font-size: 14px;
    font-weight: bold;
    margin-top: 10px;
    color: #ffffff;
}
.movie-genres {
    font-size: 12px;
    color: #bdbdbd;
}
.movie-overview {
    font-size: 11px;
    color: #cfcfcf;
    margin-top: 6px;
    height: 60px;
    overflow: hidden;
}
::-webkit-scrollbar {
    height: 8px;
}
::-webkit-scrollbar-thumb {
    background: #555;
    border-radius: 4px;
}
</style>
""", unsafe_allow_html=True)

# ---------------- LOAD DATA ----------------
@st.cache_data
def load_data():
    movies = pd.read_csv("movies.csv")  # MovieLens dataset
    movies['tags'] = movies['title'].fillna('') + " " + movies['genres'].fillna('')
    return movies

df = load_data()

# ---------------- TF-IDF & SIMILARITY ----------------
@st.cache_data
def build_similarity_matrix(tags):
    tfidf = TfidfVectorizer(stop_words="english")
    matrix = tfidf.fit_transform(tags)
    sim = cosine_similarity(matrix)
    return sim

cosine_sim = build_similarity_matrix(df['tags'])

# ---------------- OMDb API Helper ----------------
import re

def clean_title(title):
    return re.sub(r"\ \ d {4}\)$", "", title).strip()
 
@st.cache_data
def fetch_omdb_details(title):
    try:
        title_encoded = urllib.parse.quote(title)

        # Try exact title
        url = f"http://www.omdbapi.com/?t={title_encoded}&apikey={OMDB_API_KEY}"
        details = requests.get(url).json()

        # If still not found, try search
        if details.get("Response") == "False":
            url = f"http://www.omdbapi.com/?s={title_encoded}&apikey={OMDB_API_KEY}"
            res = requests.get(url).json()
            if res.get("Search"):
                imdb_id = res["Search"][0].get("imdbID")
                details = requests.get(f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}").json()

        poster = details.get("Poster", "")
        if not poster or poster == "N/A":
            poster = "https://via.placeholder.com/180x270?text=No+Poster"

        return {
            "poster": poster,
            "genres": details.get("Genre", "Unknown"),
            "overview": details.get("Plot", "No overview available."),
            "rating": details.get("imdbRating", "N/A"),
            "year": details.get("Year", "")
        }

    except Exception as e:
        return {
            "poster": "https://via.placeholder.com/180x270?text=No+Poster",
            "genres": "Unknown",
            "overview": "No data available.",
            "rating": "N/A",
            "year": ""
        }


def recommend(movie_title):
    if movie_title not in df['title'].values:
        return []
    idx = df.index[df['title'] == movie_title][0]
    sim_scores = list(enumerate(cosine_sim[idx]))
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)[1:N_RECOMMEND+1]
    recs = []
    for i, _ in sim_scores:
        row = df.iloc[i]
        omdb = fetch_omdb_details(row['title'])
        recs.append({
            "title": row['title'],
            "poster": omdb["poster"],
            "genres": omdb["genres"] if omdb["genres"] else row['genres'],
            "overview": omdb["overview"],
            "rating": omdb["rating"],
            "year": omdb["year"]
        })
    return recs

# ---------------- UI ----------------
st.markdown("<h1 style='text-align:center;'>🎬 AI-Powered Movie Recommendation System</h1>", unsafe_allow_html=True)
st.markdown("<h4 >Search a movie and get **5 similar recommendations** with posters, genres, plot, and IMDb rating (powered by OMDb API).</h4>",unsafe_allow_html=True)

query = st.text_input("🔎 Search for a movie title", "")

if st.button("RECOMMEND") and query:
    titles = df['title'].dropna().tolist()
    lower_titles = [t.lower() for t in titles]
    query_lower = query.lower()

    if query_lower in lower_titles:
        query = titles[lower_titles.index(query_lower)]
    else:
        matches = difflib.get_close_matches(query_lower, lower_titles, n=1, cutoff=0.3)
        if matches:
            query = titles[lower_titles.index(matches[0])]
        else:
            partial_matches = [t for t in titles if query_lower in t.lower()]
            if partial_matches:
                query = partial_matches[0]
            else:
                st.warning("Movie not found in dataset!")
                st.stop()

    st.subheader(f"🎥 Selected: {query}")
    recs = recommend(query)

    if recs:
        # Initialize HTML container
        cards_html = ""  # Initialize before loop
        for rec in recs:
            cards_html +=  f"""
            <div class="movie-card">
                <img src="{rec['poster']}" style="width:100%; border-radius:12px; height:270px; object-fit:cover;">
                <div class="movie-title">{rec['title']} ({rec['year']})</div>
                <div class="movie-genres">{rec['genres']} | ⭐ {rec['rating']}</div>
                <div class="movie-overview">{rec['overview'][:150]}...</div>
            </div> """
       
        st.markdown(
            f"<div style='display:flex; flex-wrap: nowrap; overflow-x:auto; gap:15px; padding:10px;'>{cards_html}</div>",
            unsafe_allow_html=True
        )
    else:
        st.warning("No recommendations found!")
