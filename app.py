import os
import tempfile
import shutil
import streamlit as st
import openai
from PyPDF2 import PdfReader
from GoogleNews import GoogleNews
from pytube import YouTube

# Set page configuration (optional)
st.set_page_config(page_title="YouTube Transcript Keyword Analyzer", page_icon="🎥", layout="wide")

# Title and introduction
st.title("🎥 YouTube Transcript Keyword Analyzer & News Explorer")
st.write(
    "Upload a transcript (PDF/TXT) or enter a YouTube link to extract key topics, then search the latest news (last 90 days) related to those topics."
)

# --- Retrieve API Keys from Streamlit Secrets ---
# For this app, you need your OpenAI API key.
openai_api_key = st.secrets.get("openai_api_key")
if not openai_api_key:
    st.error("⚠️ OpenAI API key not found! Please add your OpenAI API key in secrets.")
else:
    openai.api_key = openai_api_key

# Option to choose transcript input method
input_option = st.radio("Choose transcript input method:", ["YouTube Video URL", "Upload Transcript File"])

transcript_text = None

# If using YouTube Video URL:
if input_option == "YouTube Video URL":
    video_url = st.text_input("Enter the YouTube video URL:")
    if video_url:
        if st.button("Transcribe Video"):
            try:
                with st.spinner("Downloading and transcribing audio..."):
                    # Download audio using pytube
                    yt = YouTube(video_url)
                    audio_stream = yt.streams.filter(only_audio=True).first()
                    if audio_stream is None:
                        st.error("Unable to find an audio stream for this video.")
                    else:
                        temp_dir = tempfile.mkdtemp()
                        audio_path = os.path.join(temp_dir, "video_audio.mp4")
                        audio_stream.download(output_path=temp_dir, filename="video_audio.mp4")
                        # Transcribe using OpenAI Whisper API
                        with open(audio_path, "rb") as audio_file:
                            transcript_data = openai.Audio.transcribe("whisper-1", audio_file)
                        transcript_text = transcript_data.get("text", "")
                        # Cleanup
                        os.remove(audio_path)
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        st.success("Transcription completed!")
                        st.session_state["transcript_text"] = transcript_text
            except Exception as e:
                st.error(f"Error during transcription: {e}")

# If using file upload:
elif input_option == "Upload Transcript File":
    uploaded_file = st.file_uploader("Upload a transcript file (PDF or TXT)", type=["pdf", "txt"])
    if uploaded_file is not None:
        try:
            if uploaded_file.name.lower().endswith(".pdf"):
                reader = PdfReader(uploaded_file)
                pages = [page.extract_text() for page in reader.pages if page.extract_text() is not None]
                transcript_text = "\n".join(pages)
            else:
                transcript_text = uploaded_file.read().decode("utf-8", errors="ignore")
            st.session_state["transcript_text"] = transcript_text
        except Exception as e:
            st.error(f"Error reading file: {e}")

# If we have transcript text, proceed with keyword extraction using OpenAI GPT.
if "transcript_text" in st.session_state:
    transcript_text = st.session_state["transcript_text"]

    # (Optional) You can let users view the transcript in an expander.
    with st.expander("View Transcript (optional)"):
        st.text_area("Transcript Content:", transcript_text, height=200)

    if "keywords" not in st.session_state:
        try:
            with st.spinner("Extracting key topics from transcript..."):
                prompt_text = (
                    "Below is a transcript of a YouTube video. Extract the main topics or keywords discussed in the transcript. "
                    "Return a concise comma-separated list of key topics."
                )
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are an assistant that extracts key topics."},
                        {"role": "user", "content": prompt_text + "\n\nTranscript:\n" + transcript_text}
                    ],
                    max_tokens=100,
                    temperature=0.5,
                )
                keywords_raw = response["choices"][0]["message"]["content"]
                # Clean and split output into a list of keywords
                cleaned = keywords_raw.replace("\n", ", ").replace("Keywords:", "").replace("keywords:", "")
                keywords_list = [k.strip() for k in cleaned.split(",") if k.strip()]
                # Remove duplicates while preserving order
                seen = set()
                keywords_list = [k for k in keywords_list if not (k.lower() in seen or seen.add(k.lower()))]
                st.session_state["keywords"] = keywords_list
        except Exception as e:
            st.error(f"Error extracting keywords: {e}")

    # Display keywords and allow user to select
    if "keywords" in st.session_state and st.session_state["keywords"]:
        st.subheader("Extracted Key Topics")
        st.write("Select one or more topics to search for related news:")
        with st.form(key="news_search_form"):
            selected_keywords = st.multiselect("Keywords:", options=st.session_state["keywords"])
            submit_news = st.form_submit_button("Search Latest News")
        if submit_news:
            if selected_keywords:
                query = " ".join(selected_keywords)
                try:
                    with st.spinner("Searching for recent news articles..."):
                        # Use GoogleNews library to search articles from last 90 days
                        googlenews = GoogleNews(lang="en", region="US", period="90d")
                        googlenews.search(query)
                        results = googlenews.result()
                        googlenews.clear()
                    st.subheader(f"News Articles for: `{query}`")
                    if not results or len(results) == 0:
                        st.info("No recent news articles found for the selected topic(s).")
                    else:
                        st.markdown("""
                            <style>
                            .news-card {
                                background-color: #F9F9F9;
                                padding: 15px;
                                margin-bottom: 15px;
                                border-radius: 5px;
                                border: 1px solid #ddd;
                            }
                            .news-card a {
                                text-decoration: none;
                                color: #000;
                            }
                            .news-title {
                                font-size: 1.1em;
                                font-weight: bold;
                                margin-bottom: 5px;
                            }
                            .news-meta {
                                font-size: 0.9em;
                                color: #555;
                                margin-bottom: 8px;
                            }
                            .news-desc {
                                font-size: 0.9em;
                                color: #333;
                            }
                            </style>
                        """, unsafe_allow_html=True)
                        for item in results:
                            title = item.get("title", "Untitled")
                            source = item.get("media", "Unknown Source")
                            date = item.get("date", "")
                            description = item.get("desc", "")
                            link = item.get("link", "#")
                            news_card_html = f"""
                                <div class="news-card">
                                    <div class="news-title"><a href="{link}" target="_blank">{title}</a></div>
                                    <div class="news-meta">{source} — {date}</div>
                                    <div class="news-desc">{description}</div>
                                </div>
                            """
                            st.markdown(news_card_html, unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Error fetching news: {e}")
            else:
                st.warning("Please select at least one keyword to search for news.")
