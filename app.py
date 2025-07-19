# Save this file as api.py
# Required libraries in requirements.txt:
# fastapi
# uvicorn
# pytubefix
# python-multipart
# aiofiles

import os
import subprocess
import time
import asyncio
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pytubefix import YouTube
from pytubefix.exceptions import PytubeFixError
from starlette.background import BackgroundTasks

# --- Configuration & Setup ---

# Create a directory for temporary downloads
DOWNLOADS_DIR = "temp_downloads"
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

# Initialize FastAPI app
app = FastAPI(
    title="YouTube Downloader API",
    description="An API to fetch info and download high-quality YouTube videos by merging video and audio streams.",
    version="1.0.0",
)

# --- Helper Functions ---

def format_size(size_bytes):
    """Formats size in bytes to a readable MB format."""
    if size_bytes is None:
        return "N/A"
    return f"{round(size_bytes / (1024*1024), 2)} MB"

def combine_video_audio_ffmpeg(video_path, audio_path, output_path):
    """Merges video and audio files using a direct FFmpeg subprocess call."""
    command = [
        'ffmpeg', '-i', video_path, '-i', audio_path,
        '-c:v', 'copy', '-c:a', 'aac', '-y', output_path
    ]
    try:
        # Using asyncio.create_subprocess_exec for non-blocking execution
        process = subprocess.run(command, check=True, capture_output=True, text=True)
        print("FFmpeg stdout:", process.stdout)
        print("FFmpeg stderr:", process.stderr)
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg Error: {e.stderr}")
        raise HTTPException(status_code=500, detail=f"FFmpeg merging failed: {e.stderr}")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="FFmpeg not found on the server. Please ensure it's installed.")

def cleanup_files(*file_paths):
    """Deletes specified files from the server."""
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                print(f"Cleaned up file: {path}")
        except Exception as e:
            print(f"Error cleaning up file {path}: {e}")

# --- API Endpoints ---

@app.get("/info", summary="Get Video Information and Available Streams")
async def get_video_info(url: str = Query(..., description="The full URL of the YouTube video.")):
    """
    Fetches metadata and available stream formats for a given YouTube URL.
    It separates video-only and audio-only streams for high-quality merging.
    """
    try:
        yt = YouTube(url)
        
        # Filter for adaptive streams (video-only, no audio)
        video_streams = yt.streams.filter(
            adaptive=True, file_extension='mp4', only_video=True
        ).order_by('resolution').desc()
        
        # Filter for audio-only streams
        audio_streams = yt.streams.filter(
            adaptive=True, file_extension='mp4', only_audio=True
        ).order_by('abr').desc()

        return {
            "title": yt.title,
            "thumbnail_url": yt.thumbnail_url,
            "duration": time.strftime("%H:%M:%S", time.gmtime(yt.length)),
            "video_formats": [
                {"resolution": s.resolution, "size_mb": format_size(s.filesize), "itag": s.itag}
                for s in video_streams
            ],
            "audio_formats": [
                {"abr": s.abr, "size_mb": format_size(s.filesize), "itag": s.itag}
                for s in audio_streams
            ],
        }
    except PytubeFixError as e:
        raise HTTPException(status_code=404, detail=f"Could not process video. PytubeFix error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred: {e}")


@app.get("/download", summary="Download and Merge Video and Audio")
async def download_video(
    background_tasks: BackgroundTasks,
    url: str = Query(..., description="The full URL of the YouTube video."),
    video_itag: int = Query(..., description="The 'itag' of the desired video stream from the /info endpoint."),
    audio_itag: int = Query(..., description="The 'itag' of the desired audio stream from the /info endpoint.")
):
    """
    Downloads the selected video and audio streams, merges them with FFmpeg,
    and provides a direct link to the final file. The temporary files are cleaned up
    after the response is sent.
    """
    try:
        yt = YouTube(url)
        video_stream = yt.streams.get_by_itag(video_itag)
        audio_stream = yt.streams.get_by_itag(audio_itag)

        if not video_stream or not audio_stream:
            raise HTTPException(status_code=404, detail="Invalid video or audio itag selected.")

        sanitized_title = "".join(c for c in yt.title if c.isalnum() or c in (' ', '.', '_')).rstrip()
        
        # Define temporary file paths
        timestamp = int(time.time())
        video_filepath = video_stream.download(output_path=DOWNLOADS_DIR, filename_prefix=f"video_{timestamp}_")
        audio_filepath = audio_stream.download(output_path=DOWNLOADS_DIR, filename_prefix=f"audio_{timestamp}_")
        
        output_filename = f"{sanitized_title}_{video_stream.resolution}.mp4"
        output_filepath = os.path.join(DOWNLOADS_DIR, output_filename)

        # Merge the files
        combine_video_audio_ffmpeg(video_filepath, audio_filepath, output_filepath)

        # Add cleanup tasks to run after the response is sent
        background_tasks.add_task(cleanup_files, video_filepath, audio_filepath, output_filepath)

        return FileResponse(
            path=output_filepath,
            media_type='video/mp4',
            filename=output_filename
        )

    except PytubeFixError as e:
        raise HTTPException(status_code=404, detail=f"Could not process video. PytubeFix error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred: {e}")

# To run this API locally:
# 1. Save the code as api.py
# 2. Run in your terminal: uvicorn api:app --reload
# 3. Access the interactive API docs at http://127.0.0.1:8000/docs

"""

### How to Use This API

1.  **Deployment:** This Python script is a standalone application. You need to deploy it separately from your Node.js dashboard. You can deploy it to **Render** as a **Web Service**, but this time, you'll select **Python** as the runtime.
    * **Build Command:** `pip install -r requirements.txt`
    * **Start Command:** `uvicorn api:app --host 0.0.0.0 --port $PORT`

2.  **`requirements.txt`:** You will need a `requirements.txt` file in the same directory as `api.py` with the following content:
    ```
    fastapi
    uvicorn
    pytubefix
    python-multipart
    aiofiles
    ```

3.  **`packages.txt` (for Render):** To install FFmpeg on Render's Python environment, you'll also need a `packages.txt` file with:
    ```
    ffmpeg
    ```

4.  **Integration with Your Dashboard:**
    * You would now update your Node.js `server.js` and the YouTube downloader's `client.js`.
    * The `client.js` would first make a request to your new Python API's `/info` endpoint (e.g., `https://your-python-api.onrender.com/info?url=...`).
    * After the user selects a quality, the `client.js` would then construct the download URL pointing to your Python API's `/download` endpoint (e.g., `https://your-python-api.onrender.com/download?url=...&video_itag=...&audio_itag=...`).

This architecture is much more robust and scalable. It lets each part of your project (the Node.js dashboard and the Python API) do what it does best. 

"""