# For Streamlit Cloud, you need:
# 1. A requirements.txt file with:
#    streamlit
#    pytubefix
# 2. A packages.txt file with:
#    ffmpeg

import streamlit as st
from pytubefix import YouTube
from pytubefix.exceptions import PytubeFixError
import os
import time
import subprocess

# --- Helper Functions ---

def format_size(size_bytes):
    """Formats size in bytes to a readable MB format."""
    if size_bytes is None:
        return "N/A"
    return f"{round(size_bytes / (1024*1024), 2)} MB"

def log_message(message):
    """Appends a message to the log in session state and updates the terminal display."""
    st.session_state.log.append(message)
    st.session_state.terminal.markdown(f"```log\n{''.join(st.session_state.log)}\n```")

def combine_video_audio_ffmpeg(video_path, audio_path, output_path):
    """Merges video and audio files using a direct FFmpeg subprocess call and logs output."""
    log_message(f"[{time.strftime('%H:%M:%S')}] Starting FFmpeg merge process...\n")
    log_message(f"> ffmpeg -i video -i audio -c:v copy ...\n\n")
    
    command = [
        'ffmpeg', '-i', video_path, '-i', audio_path,
        '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental', '-y', output_path
    ]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        for line in process.stdout:
            log_message(line)
        process.wait()

        if process.returncode == 0:
            log_message(f"\n[{time.strftime('%H:%M:%S')}] FFmpeg merge successful!\n")
            return output_path
        else:
            log_message(f"\n[{time.strftime('%H:%M:%S')}] ERROR: FFmpeg process failed with exit code {process.returncode}.\n")
            return None

    except FileNotFoundError:
        log_message("[ERROR] FFmpeg not found. Ensure it's installed and in your system's PATH.\n")
        return None
    except Exception as e:
        log_message(f"[ERROR] An unexpected error occurred during merge: {e}\n")
        return None

# --- Main Application Logic ---

st.set_page_config(page_title="HQ YouTube Downloader", layout="wide")
st.title("🎬 YouTube Video Downloader with Live Terminal")

# --- Session State Initialization ---
if 'log' not in st.session_state:
    st.session_state.log = []
if 'streams' not in st.session_state:
    st.session_state.streams = None
if 'yt' not in st.session_state:
    st.session_state.yt = None
if 'download_info' not in st.session_state:
    st.session_state.download_info = None

# --- UI Layout ---
col1, col2 = st.columns([0.6, 0.4])

with col1:
    st.header("Controls")
    video_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")

    if st.button("Fetch Available Qualities"):
        # Clear previous results and log
        st.session_state.log = [f"[{time.strftime('%H:%M:%S')}] Starting process...\n"]
        st.session_state.streams = None
        st.session_state.download_info = None
        if video_url:
            try:
                with st.spinner("Fetching video details..."):
                    st.session_state.yt = YouTube(video_url)
                    st.session_state.streams = st.session_state.yt.streams.filter(file_extension='mp4').order_by('resolution').desc()
                    log_message(f"[{time.strftime('%H:%M:%S')}] Successfully fetched video: {st.session_state.yt.title}\n")
            except Exception as e:
                log_message(f"[ERROR] Could not fetch video details: {e}\n")
        else:
            st.warning("Please enter a YouTube URL.")

    if st.session_state.streams:
        stream_options = [(f"{s.resolution} ({'Video+Audio' if s.is_progressive else 'Video Only'}) - {format_size(s.filesize)}", s.itag) for s in st.session_state.streams]
        selected_option = st.radio("Select a quality to download:", options=[opt[0] for opt in stream_options])

        if st.button("Download Selected Quality"):
            selected_itag = [itag for label, itag in stream_options if label == selected_option][0]
            stream = st.session_state.yt.streams.get_by_itag(selected_itag)
            
            def on_progress(stream, chunk, bytes_remaining):
                total_size = stream.filesize
                bytes_downloaded = total_size - bytes_remaining
                percentage = (bytes_downloaded / total_size) * 100
                if percentage > st.session_state.get('last_percent', 0) + 5:
                    log_message(f"    Downloading... {int(percentage)}%\n")
                    st.session_state.last_percent = int(percentage)

            st.session_state.yt.register_on_progress_callback(on_progress)
            st.session_state.last_percent = 0

            downloads_path = 'downloads'
            if not os.path.exists(downloads_path):
                os.makedirs(downloads_path)

            sanitized_title = "".join(c for c in st.session_state.yt.title if c.isalnum() or c in (' ', '.', '_')).rstrip()
            output_filename = f"{sanitized_title} - {stream.resolution}.mp4"
            output_filepath = os.path.join(downloads_path, output_filename)

            final_video_path = None

            if stream.is_progressive:
                log_message(f"[{time.strftime('%H:%M:%S')}] Downloading {stream.resolution} (Progressive Stream)...\n")
                final_video_path = stream.download(output_path=downloads_path, filename=output_filename)
            else:
                log_message(f"[{time.strftime('%H:%M:%S')}] Downloading {stream.resolution} (Video Only)...\n")
                video_filepath = stream.download(output_path=downloads_path, filename_prefix="video_")
                log_message(f"[{time.strftime('%H:%M:%S')}] Video component download complete.\n")
                
                log_message(f"[{time.strftime('%H:%M:%S')}] Downloading best audio stream...\n")
                audio_stream = st.session_state.yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc().first()
                audio_filepath = audio_stream.download(output_path=downloads_path, filename_prefix="audio_")
                log_message(f"[{time.strftime('%H:%M:%S')}] Audio component download complete.\n")

                final_video_path = combine_video_audio_ffmpeg(video_filepath, audio_filepath, output_filepath)
                os.remove(video_filepath)
                os.remove(audio_filepath)

            if final_video_path:
                log_message(f"[{time.strftime('%H:%M:%S')}] Process complete! Video is ready.\n")
                with open(final_video_path, "rb") as file:
                    video_bytes = file.read()
                
                # Store info in session state to persist across reruns
                st.session_state.download_info = {
                    "bytes": video_bytes,
                    "filename": output_filename
                }
                # The final file is NOT deleted, so it remains in the local 'downloads' folder.

    # This block is now driven by session_state, ensuring it persists after the button click
    if st.session_state.download_info:
        st.video(st.session_state.download_info['bytes'])
        st.download_button(
            "Download Video File",
            st.session_state.download_info['bytes'],
            file_name=st.session_state.download_info['filename'],
            mime="video/mp4"
        )

with col2:
    st.header("Live Terminal Log")
    st.session_state.terminal = st.empty()
    st.session_state.terminal.markdown("```log\nWaiting for process to start...\n```")
