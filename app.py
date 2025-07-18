# For Streamlit Cloud, you need:
# 1. A requirements.txt file with:
#    streamlit
#    pytubefix
# 2. A packages.txt file with:
#    ffmpeg

import streamlit as st
from pytubefix import YouTube
from pytubefix.exceptions import PytubeFixError
from urllib.error import HTTPError
import os
import time
import subprocess

# --- Helper Functions ---

def combine_video_audio_ffmpeg(video_path, audio_path, output_path, status_text):
    """Merges video and audio files using a direct FFmpeg subprocess call."""
    status_text.text("Merging video and audio with FFmpeg...")
    command = [
        'ffmpeg', '-i', video_path, '-i', audio_path,
        '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental', '-y', output_path
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        return output_path
    except subprocess.CalledProcessError as e:
        st.error("An error occurred during the FFmpeg merge process.")
        st.error(f"FFmpeg stderr: {e.stderr}")
        return None
    except FileNotFoundError:
        st.error("FFmpeg not found. Ensure it's installed and in your system's PATH.")
        return None

def format_size(size_bytes):
    """Formats size in bytes to a readable MB format."""
    if size_bytes is None:
        return "N/A"
    return f"{round(size_bytes / (1024*1024), 2)} MB"

# --- Main Application Logic ---

st.set_page_config(page_title="HQ YouTube Downloader", layout="centered")
st.title("🎬 YouTube Video Downloader")
st.write("Paste a YouTube URL, fetch available qualities, and download your preferred version.")

# --- Session State Initialization ---
if 'streams' not in st.session_state:
    st.session_state.streams = None
if 'yt' not in st.session_state:
    st.session_state.yt = None
if 'url' not in st.session_state:
    st.session_state.url = ""

video_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")

if st.button("Fetch Available Qualities"):
    if video_url:
        st.session_state.url = video_url
        try:
            with st.spinner("Fetching video details..."):
                st.session_state.yt = YouTube(video_url)
                # Filter for mp4 files and get both adaptive and progressive streams
                st.session_state.streams = st.session_state.yt.streams.filter(file_extension='mp4').order_by('resolution').desc()
        except Exception as e:
            st.error(f"Could not fetch video details: {e}")
            st.session_state.streams = None
            st.session_state.yt = None
    else:
        st.warning("Please enter a YouTube URL.")
        st.session_state.streams = None
        st.session_state.yt = None

if st.session_state.streams:
    st.write(f"**Title:** {st.session_state.yt.title}")
    
    stream_options = []
    for s in st.session_state.streams:
        stream_type = "Video + Audio" if s.is_progressive else "Video Only"
        label = f"{s.resolution} ({stream_type}) - {format_size(s.filesize)}"
        stream_options.append((label, s.itag))

    # Use a radio button for selection
    selected_option = st.radio(
        "Select a quality to download:",
        options=[opt[0] for opt in stream_options],
        key="quality_select"
    )

    if st.button("Download Selected Quality"):
        with st.spinner('Processing... This may take a few moments.'):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Find the itag corresponding to the selected label
            selected_itag = None
            for label, itag in stream_options:
                if label == selected_option:
                    selected_itag = itag
                    break

            if selected_itag:
                stream = st.session_state.yt.streams.get_by_itag(selected_itag)
                
                downloads_path = 'downloads'
                if not os.path.exists(downloads_path):
                    os.makedirs(downloads_path)

                sanitized_title = "".join(c for c in st.session_state.yt.title if c.isalnum() or c in (' ', '.', '_')).rstrip()
                output_filename = f"{sanitized_title} - {stream.resolution}.mp4"
                output_filepath = os.path.join(downloads_path, output_filename)

                final_video_path = None

                if stream.is_progressive:
                    status_text.text(f"Downloading {stream.resolution} (Video + Audio)...")
                    final_video_path = stream.download(output_path=downloads_path, filename=output_filename)
                    progress_bar.progress(100)
                else: # It's an adaptive stream (video only)
                    status_text.text(f"Downloading {stream.resolution} (video component)...")
                    video_filepath = stream.download(output_path=downloads_path, filename_prefix="video_")
                    progress_bar.progress(50)
                    
                    status_text.text("Finding and downloading best audio component...")
                    audio_stream = st.session_state.yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc().first()
                    audio_filepath = audio_stream.download(output_path=downloads_path, filename_prefix="audio_")
                    
                    final_video_path = combine_video_audio_ffmpeg(video_filepath, audio_filepath, output_filepath, status_text)
                    os.remove(video_filepath)
                    os.remove(audio_filepath)
                
                if final_video_path:
                    progress_bar.progress(100)
                    status_text.text("Download and processing complete!")
                    st.success("Your video is ready!")

                    with open(final_video_path, "rb") as file:
                        video_bytes = file.read()
                    
                    st.video(video_bytes)
                    
                    st.download_button(
                        label="Download Video File",
                        data=video_bytes,
                        file_name=output_filename,
                        mime="video/mp4"
                    )
                    os.remove(final_video_path)

st.markdown("---")
st.markdown("Created with Streamlit and Pytubefix. Merged with FFmpeg.")
