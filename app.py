import streamlit as st
import requests
import openai
import spacy
from youtube_transcript_api import YouTubeTranscriptApi
from PyPDF2 import PdfReader
from datetime import datetime, timedelta

# Load spaCy NLP model
nlp = spacy.load("en_core_web_sm")

# Set up Streamlit app
st.set_page_config(page_title="YouTube Transcript Analyzer", layout="wide")
st.title("📊 YouTube Transcript Keyword Analyzer & News Explorer")

# Retrieve API keys from Streamlit secrets
openai_api_key = st.secrets.get("openai_api_key")
news_api_key = st.secrets.get("news_api_key")

if not openai_api_key or not news_api_key:
    st.error("⚠️ API keys missing! Ensure OpenAI & NewsAPI keys are in Streamlit secrets.")
    st.stop()
openai.api_key = openai_api_key

# -------------------- 1. Function to Get YouTube Transcript --------------------
def get_youtube_transcript(video_url):
    """Extracts transcript from a YouTube video."""
    try:
        video_id = video_url.split("v=")[-1].split("&")[0]
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        text = " ".join([entry["text"] for entry in transcript])
        return text
    except Exception as e:
        st.error(f"❌ Failed to retrieve transcript: {e}")
        return None

# -------------------- 2. Function to Extract Text from PDF or TXT --------------------
def extract_text_from_file(uploaded_file):
    """Extracts text from PDF or TXT files."""
    try:
        if uploaded_file.type == "application/pdf":
            pdf_reader = PdfReader(uploaded_file)
            text = "\n".join([page.extract_text() for page in pdf_reader.pages if page.extract_text()])
        else:
            text = uploaded_file.read().decode("utf-8", errors="ignore")
        return text
    except Exception as e:
        st.error(f"❌ Error reading file: {e}")
        return None

# -------------------- 3. Function to Extract Keywords --------------------
@st.cache_data
def extract_keywords(text):
    """Uses spaCy NLP to extract noun phrases and refines them with GPT."""
    try:
        # Extract noun phrases using spaCy
        doc = nlp(text)
        base_keywords = list(set(chunk.text.lower() for chunk in doc.noun_chunks))

        # Refine keywords with GPT
        gpt_prompt = (
            "Here is a transcript from a YouTube video. Extract the main topics discussed and return a list of keywords."
            f"\n\nTranscript:\n{text[:3000]}"  # Limit input size for efficiency
        )
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "Extract key topics."}, {"role": "user", "content": gpt_prompt}],
            max_tokens=100,
            temperature=0.5,
        )
        gpt_keywords = response["choices"][0]["message"]["content"].split(", ")
        
        # Merge & remove duplicates
        final_keywords = list(set(base_keywords + gpt_keywords))
        return sorted(final_keywords, key=lambda x: len(x), reverse=True)[:10]  # Limit to 10 keywords
    except Exception as e:
        st.error(f"❌ Error extracting keywords: {e}")
        return []

# -------------------- 4. Function to Search NewsAPI --------------------
@st.cache_data
def search_news_articles(keywords):
    """Searches for news articles related to selected keywords using NewsAPI."""
    try:
        search_query = " OR ".join(keywords)
        date_from = (datetime.today() - timedelta(days=90)).strftime("%Y-%m-%d")
        url = f"https://newsapi.org/v2/everything?q={search_query}&from={date_from}&sortBy=publishedAt&apiKey={news_api_key}"

        response = requests.get(url)
        if response.status_code == 200:
            articles = response.json().get("articles", [])[:5]  # Get top 5 articles
            return articles
        else:
            st.error("⚠️ NewsAPI request failed.")
            return []
    except Exception as e:
        st.error(f"❌ Error fetching news articles: {e}")
        return []

# -------------------- 5. UI Elements --------------------
st.subheader("Step 1: Upload Transcript or Enter YouTube URL")
input_choice = st.radio("Choose input method:", ["YouTube URL", "Upload File"])

transcript_text = None

if input_choice == "YouTube URL":
    video_url = st.text_input("Enter YouTube Video URL:")
    if video_url and st.button("Get Transcript"):
        transcript_text = get_youtube_transcript(video_url)

elif input_choice == "Upload File":
    uploaded_file = st.file_uploader("Upload a transcript file (PDF/TXT)", type=["pdf", "txt"])
    if uploaded_file:
        transcript_text = extract_text_from_file(uploaded_file)

if transcript_text:
    st.success("✅ Transcript Loaded Successfully!")
    st.session_state["transcript_text"] = transcript_text

# -------------------- 6. Extract Keywords --------------------
if "transcript_text" in st.session_state:
    st.subheader("Step 2: Extract Keywords from Transcript")
    transcript_text = st.session_state["transcript_text"]
    keywords = extract_keywords(transcript_text)

    if keywords:
        st.write("📌 **Top Keywords Identified:**")
        selected_keywords = st.multiselect("Select keywords to search for news:", keywords, default=keywords[:3])

        # -------------------- 7. Fetch News Articles --------------------
        if selected_keywords and st.button("Search News"):
            st.subheader("Step 3: Latest News Articles")
            articles = search_news_articles(selected_keywords)

            if articles:
                for article in articles:
                    st.markdown(f"""
                    **[{article['title']}]({article['url']})**  
                    🏛 {article['source']['name']} | 🗓 {article['publishedAt'][:10]}  
                    {article['description'] or ''}
                    """)
            else:
                st.info("No relevant articles found.")

st.write("🔹 *Developed for real-time YouTube transcript analysis and news tracking!*")
