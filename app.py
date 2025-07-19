# Save this file as main.py
# Required libraries in requirements.txt:
# streamlit
# fastapi
# uvicorn
# pytubefix
# python-multipart
# aiofiles
# nest-asyncio

import os
import subprocess
import time
import asyncio
import threading
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pytubefix import YouTube
from pytubefix.exceptions import PytubeFixError
from starlette.background import BackgroundTasks
from starlette.middleware.wsgi import WSGIMiddleware
import streamlit as st
import uvicorn
import nest_asyncio

# Apply nest_asyncio to allow running Streamlit and FastAPI in the same event loop
nest_asyncio.apply()

# --- Configuration & Setup ---
DOWNLOADS_DIR = "temp_downloads"
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

# --- FastAPI App ---
# Main app that will host everything
app = FastAPI(title="Main Dashboard App")

# Sub-app specifically for the API
api_app = FastAPI(
    title="YouTube Downloader API",
    description="An API to fetch info and download high-quality YouTube videos by merging video and audio streams.",
    version="1.0.0",
)

# --- Helper Functions (for both API and Streamlit) ---
def format_size(size_bytes):
    if size_bytes is None: return "N/A"
    return f"{round(size_bytes / (1024*1024), 2)} MB"

def combine_video_audio_ffmpeg(video_path, audio_path, output_path, log_func=print):
    log_func(f"[{time.strftime('%H:%M:%S')}] Starting FFmpeg merge process...")
    command = ['ffmpeg', '-i', video_path, '-i', audio_path, '-c:v', 'copy', '-c:a', 'aac', '-y', output_path]
    try:
        process = subprocess.run(command, check=True, capture_output=True, text=True)
        log_func("FFmpeg stdout: " + process.stdout)
        log_func("FFmpeg stderr: " + process.stderr)
        log_func(f"[{time.strftime('%H:%M:%S')}] FFmpeg merge successful!")
        return output_path
    except subprocess.CalledProcessError as e:
        log_func(f"FFmpeg Error: {e.stderr}")
        raise Exception(f"FFmpeg merging failed: {e.stderr}")
    except FileNotFoundError:
        raise Exception("FFmpeg not found on the server.")

def cleanup_files(*file_paths):
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                print(f"Cleaned up file: {path}")
        except Exception as e:
            print(f"Error cleaning up file {path}: {e}")

# --- FastAPI Endpoints (defined on the api_app) ---
@api_app.get("/info", summary="Get Video Information")
async def get_video_info(url: str = Query(..., description="The full URL of the YouTube video.")):
    try:
        yt = YouTube(url)
        video_streams = yt.streams.filter(adaptive=True, file_extension='mp4', only_video=True).order_by('resolution').desc()
        audio_streams = yt.streams.filter(adaptive=True, file_extension='mp4', only_audio=True).order_by('abr').desc()
        return {
            "title": yt.title, "thumbnail_url": yt.thumbnail_url, "duration": time.strftime("%H:%M:%S", time.gmtime(yt.length)),
            "video_formats": [{"resolution": s.resolution, "size_mb": format_size(s.filesize), "itag": s.itag} for s in video_streams],
            "audio_formats": [{"abr": s.abr, "size_mb": format_size(s.filesize), "itag": s.itag} for s in audio_streams],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/download", summary="Download and Merge Video")
async def download_video(background_tasks: BackgroundTasks, url: str, video_itag: int, audio_itag: int):
    try:
        yt = YouTube(url)
        video_stream = yt.streams.get_by_itag(video_itag)
        audio_stream = yt.streams.get_by_itag(audio_itag)
        if not video_stream or not audio_stream:
            raise HTTPException(status_code=404, detail="Invalid itag.")
        
        sanitized_title = "".join(c for c in yt.title if c.isalnum() or c in (' ', '.', '_')).rstrip()
        timestamp = int(time.time())
        video_filepath = video_stream.download(output_path=DOWNLOADS_DIR, filename_prefix=f"video_{timestamp}_")
        audio_filepath = audio_stream.download(output_path=DOWNLOADS_DIR, filename_prefix=f"audio_{timestamp}_")
        output_filename = f"{sanitized_title}_{video_stream.resolution}.mp4"
        output_filepath = os.path.join(DOWNLOADS_DIR, output_filename)

        combine_video_audio_ffmpeg(video_filepath, audio_filepath, output_filepath)
        background_tasks.add_task(cleanup_files, video_filepath, audio_filepath, output_filepath)
        return FileResponse(path=output_filepath, media_type='video/mp4', filename=output_filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Streamlit App ---
# The Streamlit UI code is now defined in a function
def run_streamlit():
    st.set_page_config(page_title="HQ YouTube Downloader", layout="wide")
    st.title("🎬 YouTube Video Downloader & API")

    # --- Session State Initialization ---
    if 'log' not in st.session_state: st.session_state.log = []
    if 'streams' not in st.session_state: st.session_state.streams = None
    if 'yt' not in st.session_state: st.session_state.yt = None
    if 'download_info' not in st.session_state: st.session_state.download_info = None
    
    tab1, tab2 = st.tabs(["🚀 Live Downloader", "🔌 API Usage"])

    with tab1:
        col1, col2 = st.columns([0.6, 0.4])
        with col1:
            st.header("Controls")
            video_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")

            def log_message(message):
                st.session_state.log.append(message)
                st.session_state.terminal.markdown(f"```log\n{''.join(st.session_state.log)}\n```")

            if st.button("Fetch Available Qualities"):
                st.session_state.log = [f"[{time.strftime('%H:%M:%S')}] Starting process...\n"]
                st.session_state.streams = None
                st.session_state.download_info = None
                if video_url:
                    try:
                        with st.spinner("Fetching video details..."):
                            st.session_state.yt = YouTube(video_url)
                            st.session_state.streams = st.session_state.yt.streams.filter(file_extension='mp4').order_by('resolution').desc()
                            log_message(f"[{time.strftime('%H:%M:%S')}] Fetched: {st.session_state.yt.title}\n")
                    except Exception as e:
                        log_message(f"[ERROR] Could not fetch details: {e}\n")
                else:
                    st.warning("Please enter a YouTube URL.")

            if st.session_state.streams:
                stream_options = [(f"{s.resolution} ({'Video+Audio' if s.is_progressive else 'Video Only'}) - {format_size(s.filesize)}", s.itag) for s in st.session_state.streams]
                selected_option = st.radio("Select a quality:", options=[opt[0] for opt in stream_options])

                if st.button("Download Selected Quality"):
                    selected_itag = [itag for label, itag in stream_options if label == selected_option][0]
                    stream = st.session_state.yt.streams.get_by_itag(selected_itag)
                    
                    sanitized_title = "".join(c for c in st.session_state.yt.title if c.isalnum() or c in (' ', '.', '_')).rstrip()
                    output_filename = f"{sanitized_title} - {stream.resolution}.mp4"
                    output_filepath = os.path.join(DOWNLOADS_DIR, output_filename)
                    
                    final_video_path = None
                    with st.spinner("Downloading... Please check the terminal for progress."):
                        if stream.is_progressive:
                            log_message(f"[{time.strftime('%H:%M:%S')}] Downloading progressive stream...\n")
                            final_video_path = stream.download(output_path=DOWNLOADS_DIR, filename=output_filename)
                        else:
                            log_message(f"[{time.strftime('%H:%M:%S')}] Downloading video-only stream...\n")
                            video_filepath = stream.download(output_path=DOWNLOADS_DIR, filename_prefix="video_")
                            log_message(f"[{time.strftime('%H:%M:%S')}] Downloading best audio stream...\n")
                            audio_stream = st.session_state.yt.streams.get_audio_only()
                            audio_filepath = audio_stream.download(output_path=DOWNLOADS_DIR, filename_prefix="audio_")
                            final_video_path = combine_video_audio_ffmpeg(video_filepath, audio_filepath, output_filepath, log_func=log_message)
                            cleanup_files(video_filepath, audio_filepath)

                    if final_video_path:
                        log_message(f"[{time.strftime('%H:%M:%S')}] Process complete! Video is ready.\n")
                        with open(final_video_path, "rb") as file:
                            st.session_state.download_info = {"bytes": file.read(), "filename": output_filename}
                        cleanup_files(final_video_path)

            if st.session_state.download_info:
                st.video(st.session_state.download_info['bytes'])
                st.download_button("Download Video File", st.session_state.download_info['bytes'], file_name=st.session_state.download_info['filename'], mime="video/mp4")

        with col2:
            st.header("Live Terminal Log")
            st.session_state.terminal = st.empty()
            st.session_state.terminal.markdown("```log\nWaiting for process to start...\n```")
    
    with tab2:
        st.header("API Documentation")
        st.markdown("You can use this service programmatically. Here are the available endpoints:")
        st.subheader("`GET /api/info`")
        st.markdown("Fetches video metadata and available formats.")
        st.code("https://your-app-url/api/info?url=YOUTUBE_URL")
        st.subheader("`GET /api/download`")
        st.markdown("Downloads and merges the selected video and audio streams.")
        st.code("https://your-app-url/api/download?url=YOUTUBE_URL&video_itag=ITAG&audio_itag=ITAG")

# --- Main App Mounting ---
# Mount the API routes under the '/api' path on the main FastAPI app
app.mount("/api", api_app)

# Create a temporary file to run the Streamlit app
with open("streamlit_app.py", "w") as f:
    f.write("import main\nmain.run_streamlit()")

# Mount the Streamlit app as a WSGI application at the root
app.mount("/", WSGIMiddleware(os.popen("streamlit run streamlit_app.py --server.headless true")._stream))

# To run this unified app:
# 1. Save the code as main.py
# 2. Run in your terminal: uvicorn main:app --reload
# 3. Access the Streamlit UI at http://127.0.0.1:8000/
# 4. Access the API docs at http://127.0.0.1:8000/api/docs
