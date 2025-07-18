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

def combine_video_audio_ffmpeg(video_path, audio_path, output_path, status_text):
    """Merges video and audio files using a direct FFmpeg subprocess call."""
    status_text.text("Merging video and audio with FFmpeg...")
    
    # The FFmpeg command
    command = [
        'ffmpeg',
        '-i', video_path,
        '-i', audio_path,
        '-c:v', 'copy',      # Copy the video stream without re-encoding
        '-c:a', 'aac',       # Re-encode audio to AAC (a safe, compatible choice)
        '-strict', 'experimental',
        '-y',                # Overwrite output file if it exists
        output_path
    ]
    
    try:
        # Execute the command
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        st.info("FFmpeg stdout: " + result.stdout)
        st.info("FFmpeg stderr: " + result.stderr)
        return output_path
    except subprocess.CalledProcessError as e:
        # This block will run if FFmpeg returns a non-zero exit code (an error)
        st.error("An error occurred during the FFmpeg merge process.")
        st.error(f"FFmpeg command failed with exit code {e.returncode}")
        st.error("FFmpeg stderr: " + e.stderr)
        st.error("FFmpeg stdout: " + e.stdout)
        return None
    except FileNotFoundError:
        st.error("FFmpeg not found. Please ensure it is installed and in your system's PATH.")
        st.error("If on Streamlit Cloud, ensure you have a packages.txt file with 'ffmpeg' in it.")
        return None


def download_hq_video(url, progress_bar, status_text):
    """
    Downloads the highest quality video and audio from a YouTube URL,
    merges them using FFmpeg, and provides a download link and video player.
    """
    try:
        # --- Create a 'downloads' directory ---
        downloads_path = 'downloads'
        if not os.path.exists(downloads_path):
            os.makedirs(downloads_path)

        # --- YouTube Object ---
        yt = YouTube(url)
        st.write(f"**Title:** {yt.title}")
        status_text.text(f"Fetching streams for: {yt.title}")
        time.sleep(1)

        # --- Stream Selection (Highest Quality) ---
        status_text.text("Finding the best video stream...")
        video_stream = yt.streams.filter(adaptive=True, file_extension='mp4').order_by('resolution').desc().first()
        
        status_text.text("Finding the best audio stream...")
        audio_stream = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc().first()

        if not video_stream or not audio_stream:
            st.error("Could not find high-quality adaptive streams. Please try another video.")
            return

        st.write(f"Video Stream: {video_stream.resolution}, {round(video_stream.filesize / (1024*1024), 2)} MB")
        st.write(f"Audio Stream: {audio_stream.abr}, {round(audio_stream.filesize / (1024*1024), 2)} MB")

        # --- Download Streams ---
        status_text.text("Downloading video component...")
        video_filepath = video_stream.download(output_path=downloads_path, filename_prefix="video_")
        
        status_text.text("Downloading audio component...")
        audio_filepath = audio_stream.download(output_path=downloads_path, filename_prefix="audio_")

        # --- Combine Files ---
        progress_bar.progress(50)
        
        sanitized_title = "".join(c for c in yt.title if c.isalnum() or c in (' ', '.', '_')).rstrip()
        output_filename = f"{sanitized_title}.mp4"
        output_filepath = os.path.join(downloads_path, output_filename)
        
        final_video_path = combine_video_audio_ffmpeg(video_filepath, audio_filepath, output_filepath, status_text)
        
        if final_video_path is None:
            return # Stop if merging failed

        progress_bar.progress(100)
        status_text.text("Merge complete!")
        st.success("High-quality video is ready!")

        # --- Read the final video file for playback and download ---
        with open(final_video_path, "rb") as file:
            video_bytes = file.read()

        # --- Display the video player ---
        st.video(video_bytes)

        # --- Provide Download Link ---
        st.download_button(
            label="Download HQ Video File",
            data=video_bytes,
            file_name=output_filename,
            mime="video/mp4"
        )

        # --- Cleanup ---
        os.remove(video_filepath)
        os.remove(audio_filepath)
        os.remove(final_video_path)

    except HTTPError as e:
        st.error(f"Network Error: {e}")
    except PytubeFixError as e:
        st.error(f"PytubeFix Error: {e}")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")

# --- Streamlit App UI ---
st.set_page_config(page_title="HQ YouTube Downloader", layout="centered")
st.title("🎬 High-Quality YouTube Downloader")
st.write("Paste a YouTube video URL below to download the highest resolution video with audio.")

video_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")

if st.button("Download Video"):
    if video_url:
        with st.spinner('Processing... This may take a few moments.'):
            progress_bar = st.progress(0)
            status_text = st.empty()
            download_hq_video(video_url, progress_bar, status_text)
    else:
        st.warning("Please enter a YouTube URL.")

st.markdown("---")
st.markdown("Created with Streamlit and Pytubefix. Merged with FFmpeg.")
