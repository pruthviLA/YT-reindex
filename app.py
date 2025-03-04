import os
import streamlit as st
import requests
import json
import re
import datetime
import nltk
import string
from collections import Counter
from io import BytesIO
import PyPDF2

# -------------------------------------------------
# Set up a local NLTK data directory and ensure required resources are available
# -------------------------------------------------
nltk_data_dir = "./nltk_data"
if not os.path.exists(nltk_data_dir):
    os.makedirs(nltk_data_dir)
os.environ["NLTK_DATA"] = nltk_data_dir
if nltk_data_dir not in nltk.data.path:
    nltk.data.path.append(nltk_data_dir)

# Force download required NLTK packages into the local directory
nltk.download("punkt", quiet=True, download_dir=nltk_data_dir)
nltk.download("stopwords", quiet=True, download_dir=nltk_data_dir)

from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

# -------------------------------------------------
# Load API key from Streamlit secrets
# Make sure you have a .streamlit/secrets.toml file with:
# [api_keys]
# GOOGLE_NEWS_API_KEY = "your-google-news-api-key"
# -------------------------------------------------
GOOGLE_NEWS_API_KEY = st.secrets["api_keys"]["GOOGLE_NEWS_API_KEY"]

st.title("News Keyword Explorer & Modern News Cards")
st.markdown("Upload a YouTube Transcript (PDF or TXT) or paste the transcript below:")

# --- Upload file or paste text ---
uploaded_file = st.file_uploader("Upload a file", type=["pdf", "txt"])

transcript_text = ""
if uploaded_file is not None:
    file_type = uploaded_file.type
    if file_type == "application/pdf":
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        transcript_text = ""
        for page in pdf_reader.pages:
            transcript_text += page.extract_text() + "\n"
    elif file_type == "text/plain":
        transcript_text = uploaded_file.read().decode("utf-8")
else:
    transcript_text = st.text_area("Or paste transcript text here:", height=200)

if transcript_text:
    st.markdown("### Extracting & Sorting Keywords")
    # Tokenize the transcript and filter out punctuation and stopwords
    tokens = word_tokenize(transcript_text.lower())
    stop_words = set(stopwords.words("english"))
    tokens = [token for token in tokens if token not in string.punctuation and token not in stop_words]
    word_counts = Counter(tokens)
    sorted_keywords = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    
    # Display the top 20 keywords
    top_keywords = [word for word, count in sorted_keywords[:20]]
    st.markdown("#### Top Keywords:")
    st.write(top_keywords)
    
    # Allow user to select which keywords to search for news
    selected_keywords = st.multiselect("Select keywords to search for news:", top_keywords, default=top_keywords[:5])
    
    if selected_keywords:
        st.markdown("### Searching Google News for Selected Keywords")
        all_news = {}
        # Calculate date 90 days ago
        current_date = datetime.datetime.now()
        date_90_days_ago = current_date - datetime.timedelta(days=90)
        from_date = date_90_days_ago.strftime("%Y-%m-%d")
        
        # For each keyword, query the Google News API
        for keyword in selected_keywords:
            url = (
                f"https://newsapi.org/v2/everything?q={keyword}&from={from_date}"
                f"&sortBy=publishedAt&apiKey={GOOGLE_NEWS_API_KEY}"
            )
            response = requests.get(url)
            data = response.json()
            if data.get("status") == "ok":
                articles = data.get("articles", [])
                all_news[keyword] = articles
            else:
                all_news[keyword] = []
        
        st.markdown("### News Results")
        # Display results for each keyword as modern cards
        for keyword, articles in all_news.items():
            st.markdown(f"#### News for keyword: **{keyword}**")
            if articles:
                for article in articles:
                    title = article.get("title", "No Title")
                    description = article.get("description", "No Description Available")
                    url_link = article.get("url", "#")
                    published_at = article.get("publishedAt", "")
                    source_name = article.get("source", {}).get("name", "Unknown Source")
                    
                    # Modern card styling using HTML & CSS
                    card_html = f"""
                    <div style="
                        border: 1px solid #ddd;
                        border-radius: 10px;
                        padding: 15px;
                        margin-bottom: 15px;
                        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
                        background-color: #f9f9f9;
                    ">
                        <h3 style="margin: 0;">
                            <a href="{url_link}" target="_blank" style="text-decoration: none; color: #333;">
                                {title}
                            </a>
                        </h3>
                        <p style="margin: 5px 0; font-size: 0.9em; color: #555;">
                            <strong>{source_name}</strong> | {published_at}
                        </p>
                        <p style="margin: 5px 0;">{description}</p>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
            else:
                st.write("No articles found for this keyword.")
