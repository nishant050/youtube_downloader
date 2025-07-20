# For Streamlit Cloud, you need:
# 1. A requirements.txt file with:
#    streamlit
#    pytubefix
# 2. A packages.txt file with:
#    ffmpeg

import streamlit as st
from pytubefix import YouTube
import os
import time
import subprocess

# --- Page Configuration ---
st.set_page_config(
    page_title="Pro Downloader",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Custom CSS for a more polished look ---
st.markdown("""
<style>
    /* General Styles */
    .stApp {
        background-color: #f0f2f6;
    }
    .stButton>button {
        border-radius: 20px;
        border: 1px solid #4B8BF5;
        background-color: #4B8BF5;
        color: white;
        transition: all 0.2s ease-in-out;
    }
    .stButton>button:hover {
        background-color: #4A7EE5;
        border-color: #4A7EE5;
        transform: scale(1.02);
    }
    .stButton>button:active {
        background-color: #3e6dcf;
        border-color: #3e6dcf;
    }
    .stTextInput>div>div>input {
        border-radius: 20px;
        border: 1px solid #ced4da;
    }
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 10px;
        padding: 15px;
    }
    [data-testid="stExpander"] {
        border-radius: 10px;
        border: 1px solid #E0E0E0;
    }
    .terminal {
        background-color: #2b2b2b;
        color: #f0f0f0;
        font-family: 'Courier New', Courier, monospace;
        padding: 1rem;
        border-radius: 10px;
        height: 400px;
        overflow-y: auto;
        border: 1px solid #444;
    }
</style>
""", unsafe_allow_html=True)


# --- Helper Functions ---

def format_size(size_bytes):
    """Formats size in bytes to a readable MB format."""
    if size_bytes is None:
        return "N/A"
    return f"{round(size_bytes / (1024*1024), 2)} MB"

def log_message(message):
    """Appends a message to the log in session state and updates the terminal display."""
    timestamp = time.strftime('%H:%M:%S')
    st.session_state.log.append(f"[{timestamp}] {message}\n")
    # Keep the log from getting too long
    if len(st.session_state.log) > 100:
        st.session_state.log = st.session_state.log[-100:]
    st.session_state.terminal_display.markdown(f"<div class='terminal'><pre>{''.join(st.session_state.log)}</pre></div>", unsafe_allow_html=True)

def combine_video_audio_ffmpeg(video_path, audio_path, output_path):
    """Merges video and audio files using FFmpeg and logs the output."""
    log_message("Starting FFmpeg merge process...")
    log_message(f"Command: ffmpeg -i video.mp4 -i audio.mp4 -c:v copy -c:a aac -y out.mp4")
    
    command = [
        'ffmpeg', '-i', video_path, '-i', audio_path,
        '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental', '-y', output_path
    ]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, text=True)
        for line in process.stdout:
            log_message(f"FFMPEG: {line.strip()}")
        process.wait()

        if process.returncode == 0:
            log_message("FFmpeg merge successful!")
            return output_path
        else:
            log_message(f"ERROR: FFmpeg process failed with exit code {process.returncode}.")
            return None
    except FileNotFoundError:
        st.error("ffmpeg not found. Please ensure it is installed and in your system's PATH.")
        log_message("[ERROR] FFmpeg not found. It must be installed on the system.")
        return None
    except Exception as e:
        log_message(f"[ERROR] An unexpected error occurred during merge: {e}")
        return None

def reset_state():
    """Clears the session state to start over."""
    for key in list(st.session_state.keys()):
        # Keep essential keys if needed, otherwise clear all
        if key not in ['log', 'terminal_display']:
             del st.session_state[key]
    st.session_state.log = ["Welcome! Waiting for process to start...\n"]
    if 'terminal_display' in st.session_state:
        st.session_state.terminal_display.markdown(f"<div class='terminal'><pre>{''.join(st.session_state.log)}</pre></div>", unsafe_allow_html=True)


# --- Session State Initialization ---
if 'log' not in st.session_state:
    st.session_state.log = ["Welcome! Waiting for process to start...\n"]
if 'yt' not in st.session_state:
    st.session_state.yt = None
if 'download_info' not in st.session_state:
    st.session_state.download_info = None
if 'video_streams' not in st.session_state:
    st.session_state.video_streams = []
if 'audio_streams' not in st.session_state:
    st.session_state.audio_streams = []


# --- Main Application UI ---
st.title("🎬 Advanced YouTube Downloader")
st.markdown("Enter a YouTube URL to fetch download options. High-quality video and audio are downloaded separately and merged automatically.")

# --- UI Layout ---
main_col, terminal_col = st.columns([0.55, 0.45], gap="large")

with main_col:
    # --- Input and Controls ---
    with st.container(border=True):
        st.subheader("1. Enter URL")
        url_col, btn_col = st.columns([0.75, 0.25])
        with url_col:
            video_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...", label_visibility="collapsed")
        with btn_col:
            fetch_btn = st.button("Fetch Info", use_container_width=True)

        if fetch_btn:
            reset_state() # Reset on new fetch
            if video_url:
                with st.spinner("Fetching video details..."):
                    try:
                        log_message(f"Fetching details for: {video_url}")
                        st.session_state.yt = YouTube(video_url)
                        
                        # Filter streams
                        all_streams = st.session_state.yt.streams
                        st.session_state.video_streams = all_streams.filter(file_extension='mp4', type="video").order_by('resolution').desc()
                        st.session_state.audio_streams = all_streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc()
                        
                        log_message(f"Successfully fetched video: {st.session_state.yt.title}")
                    except Exception as e:
                        st.error(f"Error fetching video: {e}")
                        log_message(f"[ERROR] Could not fetch video details: {e}")
            else:
                st.warning("Please enter a YouTube URL.")

    # --- Display Fetched Info and Download Options ---
    if st.session_state.yt:
        with st.container(border=True):
            st.subheader("2. Select Quality & Download")
            info_col, thumb_col = st.columns([0.7, 0.3])
            with info_col:
                st.metric("Video Title", st.session_state.yt.title)
                st.metric("Author", st.session_state.yt.author, delta=f"{st.session_state.yt.views:,} views")
            with thumb_col:
                st.image(st.session_state.yt.thumbnail_url, use_column_width=True)

            video_tab, audio_tab = st.tabs(["🎬 Video Download", "🎵 Audio Only"])

            # --- Video Download Tab ---
            with video_tab:
                if st.session_state.video_streams:
                    video_options = {
                        f"{s.resolution} ({'Video+Audio' if s.is_progressive else 'Video Only'}) - {format_size(s.filesize)}": s.itag
                        for s in st.session_state.video_streams
                    }
                    selected_video_label = st.radio("Select a video quality:", options=video_options.keys(), key="video_choice")

                    if st.button("Download Video", key="download_video_btn", use_container_width=True):
                        selected_itag = video_options[selected_video_label]
                        stream = st.session_state.yt.streams.get_by_itag(selected_itag)
                        
                        st.session_state.download_info = None # Clear previous downloads
                        
                        def on_progress(stream, chunk, bytes_remaining):
                            total_size = stream.filesize
                            bytes_downloaded = total_size - bytes_remaining
                            percentage = (bytes_downloaded / total_size) * 100
                            if percentage > st.session_state.get('last_percent', 0) + 10:
                                log_message(f"Downloading... {int(percentage)}%")
                                st.session_state.last_percent = int(percentage)

                        st.session_state.yt.register_on_progress_callback(on_progress)
                        st.session_state.last_percent = 0

                        downloads_path = 'downloads'
                        if not os.path.exists(downloads_path):
                            os.makedirs(downloads_path)
                        
                        sanitized_title = "".join(c for c in st.session_state.yt.title if c.isalnum() or c in (' ', '.', '_')).rstrip()
                        
                        with st.spinner("Downloading... Check terminal for progress."):
                            final_video_path = None
                            if stream.is_progressive:
                                log_message(f"Downloading {stream.resolution} (Progressive Stream)...")
                                output_filename = f"{sanitized_title} - {stream.resolution}.mp4"
                                final_video_path = stream.download(output_path=downloads_path, filename=output_filename)
                            else: # Adaptive stream (video only)
                                log_message(f"Downloading {stream.resolution} (Video Only)...")
                                video_filepath = stream.download(output_path=downloads_path, filename_prefix="video_")
                                log_message("Video component download complete.")
                                
                                log_message("Downloading best audio stream...")
                                audio_stream = st.session_state.yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc().first()
                                audio_filepath = audio_stream.download(output_path=downloads_path, filename_prefix="audio_")
                                log_message("Audio component download complete.")

                                output_filename = f"{sanitized_title} - {stream.resolution}.mp4"
                                output_filepath = os.path.join(downloads_path, output_filename)
                                
                                final_video_path = combine_video_audio_ffmpeg(video_filepath, audio_filepath, output_filepath)
                                if final_video_path:
                                    os.remove(video_filepath)
                                    os.remove(audio_filepath)

                            if final_video_path:
                                log_message("Process complete! Video is ready.")
                                with open(final_video_path, "rb") as file:
                                    video_bytes = file.read()
                                st.session_state.download_info = {"bytes": video_bytes, "filename": output_filename, "type": "video"}
                else:
                    st.info("No MP4 video streams found for this video.")

            # --- Audio Download Tab ---
            with audio_tab:
                if st.session_state.audio_streams:
                    audio_options = {
                        f"{s.abr} ({s.mime_type}) - {format_size(s.filesize)}": s.itag
                        for s in st.session_state.audio_streams
                    }
                    selected_audio_label = st.radio("Select an audio quality:", options=audio_options.keys(), key="audio_choice")

                    if st.button("Download Audio", key="download_audio_btn", use_container_width=True):
                        selected_itag = audio_options[selected_audio_label]
                        stream = st.session_state.yt.streams.get_by_itag(selected_itag)
                        
                        st.session_state.download_info = None # Clear previous downloads

                        downloads_path = 'downloads'
                        if not os.path.exists(downloads_path):
                            os.makedirs(downloads_path)
                        
                        sanitized_title = "".join(c for c in st.session_state.yt.title if c.isalnum() or c in (' ', '.', '_')).rstrip()
                        output_filename = f"{sanitized_title} - {stream.abr}.mp3"
                        output_filepath = os.path.join(downloads_path, output_filename)

                        with st.spinner("Downloading audio..."):
                            log_message(f"Downloading audio ({stream.abr})...")
                            temp_path = stream.download(output_path=downloads_path)
                            
                            # Convert to MP3 using ffmpeg for wider compatibility
                            log_message(f"Converting to MP3...")
                            command = ['ffmpeg', '-i', temp_path, '-q:a', '0', '-map', 'a', '-y', output_filepath]
                            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            os.remove(temp_path) # Clean up original download

                            log_message("Audio download and conversion complete!")
                            with open(output_filepath, "rb") as file:
                                audio_bytes = file.read()
                            st.session_state.download_info = {"bytes": audio_bytes, "filename": output_filename, "type": "audio"}
                else:
                    st.info("No MP4 audio streams found for this video.")

    # --- Display Downloaded File ---
    if st.session_state.download_info:
        with st.container(border=True):
            st.subheader("3. Your File is Ready!")
            info = st.session_state.download_info
            if info['type'] == 'video':
                st.video(info['bytes'])
            elif info['type'] == 'audio':
                st.audio(info['bytes'], format='audio/mp3')
            
            st.download_button(
                label="📥 Download File",
                data=info['bytes'],
                file_name=info['filename'],
                mime="video/mp4" if info['type'] == 'video' else "audio/mp3",
                use_container_width=True
            )

with terminal_col:
    st.subheader("Live Terminal Log")
    st.session_state.terminal_display = st.empty()
    st.session_state.terminal_display.markdown(f"<div class='terminal'><pre>{''.join(st.session_state.log)}</pre></div>", unsafe_allow_html=True)
    if st.button("Clear Log & Reset", use_container_width=True):
        reset_state()
        st.rerun()

