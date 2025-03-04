import os
import tempfile
import shutil
import streamlit as st
import openai
from PyPDF2 import PdfReader
from GoogleNews import GoogleNews
from pytube import YouTube

# Set page configuration (optional)
st.set_page_config(page_title="YouTube Transcript Analyzer", page_icon="🎥", layout="wide")

# Title and introduction
st.title("🎥 YouTube Transcript Keyword Analyzer & News Explorer")
st.write(
    "Upload a YouTube transcript (PDF/TXT) or enter a YouTube link to extract key topics, "
    "then search the latest news (last 90 days) related to those topics."
)

# Securely get API keys from Streamlit secrets
openai_api_key = st.secrets.get("openai_api_key")  # Ensure this key is set in Streamlit secrets
if not openai_api_key:
    st.error("⚠️ OpenAI API key not found! Please add your OpenAI API key to Streamlit secrets.")
else:
    openai.api_key = openai_api_key

# Option to choose input method
input_option = st.radio("Choose transcript input method:", ["YouTube Video URL", "Upload Transcript File"])

transcript_text = None

# If user chooses YouTube URL input
if input_option == "YouTube Video URL":
    video_url = st.text_input("Enter the YouTube video URL:")
    if video_url:
        # Button to trigger transcription
        if st.button("Transcribe Video"):
            try:
                with st.spinner("Transcribing audio with Whisper (this may take a moment)..."):
                    # Download the video's audio stream using pytube
                    yt = YouTube(video_url)
                    audio_stream = yt.streams.filter(only_audio=True).first()
                    if audio_stream is None:
                        st.error("Unable to find an audio stream for this video.")
                    else:
                        # Download audio to a temporary file
                        temp_dir = tempfile.mkdtemp()
                        audio_path = os.path.join(temp_dir, "video_audio.mp4")
                        audio_stream.download(output_path=temp_dir, filename="video_audio.mp4")
                        # Use OpenAI Whisper API to transcribe audio
                        with open(audio_path, "rb") as audio_file:
                            transcript_data = openai.Audio.transcribe("whisper-1", audio_file)
                        # Clean up the temporary file
                        os.remove(audio_path)
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        # Extract transcribed text
                        transcript_text = transcript_data.get("text", "")
            except Exception as e:
                st.error(f"Error during transcription: {e}")
    
    # Store the transcript in session state if obtained
    if transcript_text:
        st.session_state["transcript_text"] = transcript_text

# If user chooses file upload input
elif input_option == "Upload Transcript File":
    uploaded_file = st.file_uploader("Upload a transcript file (PDF or TXT)", type=["pdf", "txt"])
    if uploaded_file is not None:
        try:
            # Determine file type and read content
            if uploaded_file.name.lower().endswith(".pdf"):
                # Read PDF file
                reader = PdfReader(uploaded_file)
                text_pages = [page.extract_text() for page in reader.pages]
                transcript_text = "\n".join(filter(None, text_pages))  # join non-empty pages
            else:
                # Read TXT file
                bytes_data = uploaded_file.read()
                transcript_text = bytes_data.decode("utf-8", errors="ignore")
        except Exception as e:
            st.error(f"Error reading file: {e}")
        
        if transcript_text:
            st.session_state["transcript_text"] = transcript_text

# If we have transcript text (from either method), proceed to keyword extraction
if "transcript_text" in st.session_state:
    transcript_text = st.session_state["transcript_text"]
    
    # Optionally, display the transcript in an expandable text area for user reference
    with st.expander("View Transcript Text"):
        st.text_area("Transcript Content:", transcript_text, height=200)
    
    # Extract keywords using GPT (only if not already done for this transcript)
    if "keywords" not in st.session_state:
        try:
            with st.spinner("Extracting key topics from the transcript..."):
                # Prepare prompt for GPT
                prompt_text = (
                    "Below is a transcript of a YouTube video. "
                    "Extract the main topics or keywords discussed in this transcript. "
                    "Provide a concise list of the most important keywords or key phrases, separated by commas."
                )
                # Call OpenAI GPT (ChatCompletion) to get keywords
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are an assistant that extracts key topics from transcripts."},
                        {"role": "user", "content": prompt_text + "\n\nTranscript:\n" + transcript_text}
                    ],
                    max_tokens=100,
                    temperature=0.5,
                )
                keywords_raw = response["choices"][0]["message"]["content"]
                # Process the GPT output into a list of keywords
                # Remove any introductory words like "Keywords:" and split by commas/newlines
                cleaned = keywords_raw.replace("\n", ", ").replace("Keywords:", "").replace("keywords:", "")
                # Split and strip each keyword/phrase
                keywords_list = [k.strip() for k in cleaned.split(",") if k.strip()]
                # Remove duplicates while preserving order
                seen = set()
                keywords_list = [k for k in keywords_list if not (k.lower() in seen or seen.add(k.lower()))]
                st.session_state["keywords"] = keywords_list
        except Exception as e:
            st.error(f"Error extracting keywords: {e}")
    
    # If keywords are available, show them for selection
    if "keywords" in st.session_state and st.session_state["keywords"]:
        st.subheader("Extracted Key Topics")
        st.write("Select one or more topics to search for related news articles:")
        
        # Use a form with multiselect to allow multiple keyword selection and a search trigger
        with st.form(key="news_search_form"):
            selected_keywords = st.multiselect("Keywords:", options=st.session_state["keywords"])
            search_news = st.form_submit_button("Search Latest News")
        
        # If the search button is pressed, query the news API (Google News)
        if search_news:
            if selected_keywords:
                query = " ".join(selected_keywords)
                try:
                    with st.spinner("Searching for recent news articles..."):
                        # Initialize GoogleNews API and search for the query in the last 90 days
                        googlenews = GoogleNews(lang="en", region="US", period="90d")
                        googlenews.search(query)
                        results = googlenews.result()  # retrieve results for the search query
                        # Clear the GoogleNews object (not strictly necessary since we won't reuse it)
                        googlenews.clear()
                    # Display results if any
                    st.subheader(f"News Articles for: `{query}`")
                    if not results or len(results) == 0:
                        st.info("No recent news articles found for the selected topic(s).")
                    else:
                        # Define a simple card-like style for news results
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
                        # Iterate through news results and display each as a card
                        for item in results:
                            title = item.get("title", "Untitled")
                            source = item.get("media", "Unknown Source")
                            date = item.get("date", "")
                            description = item.get("desc", "")
                            link = item.get("link", "")
                            # Construct a news card for each result
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
