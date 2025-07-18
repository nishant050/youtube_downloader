# To run this app, you need to install streamlit, pytubefix, and moviepy:
# pip install streamlit pytubefix moviepy
#
# Then, save this code as a Python file (e.g., app.py) and run from your terminal:
# streamlit run app.py
#
# For Streamlit Cloud, you also need a packages.txt file with "ffmpeg" in it.

import streamlit as st
from pytubefix import YouTube
from pytubefix.exceptions import PytubeFixError
from urllib.error import HTTPError
import os
import time
from moviepy.editor import VideoFileClip, AudioFileClip

def combine_video_audio(video_path, audio_path, output_path, status_text):
    """Merges video and audio files using MoviePy."""
    status_text.text("Merging video and audio... This may take a moment.")
    try:
        video_clip = VideoFileClip(video_path)
        audio_clip = AudioFileClip(audio_path)
        final_clip = video_clip.set_audio(audio_clip)
        final_clip.write_videofile(output_path, codec='libx264', audio_codec='aac', logger=None) # Set logger to None to avoid progress bars in console
        video_clip.close()
        audio_clip.close()
        return output_path
    except Exception as e:
        st.error(f"Error during merge process: {e}")
        return None


def download_hq_video(url, progress_bar, status_text):
    """
    Downloads the highest quality video and audio from a YouTube URL,
    merges them, and provides a download link and video player.
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
        progress_bar.progress(50) # Show some progress
        
        sanitized_title = "".join(c for c in yt.title if c.isalnum() or c in (' ', '.', '_')).rstrip()
        output_filename = f"{sanitized_title}.mp4"
        output_filepath = os.path.join(downloads_path, output_filename)
        
        final_video_path = combine_video_audio(video_filepath, audio_filepath, output_filepath, status_text)
        
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
        os.remove(final_video_path) # Safely remove the final file after reading it into memory

    except HTTPError as e:
        st.error(f"Network Error: {e}")
        st.warning("This could be an invalid URL, an age-restricted video, or a temporary YouTube issue.")
    except PytubeFixError as e:
        st.error(f"PytubeFix Error: {e}")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        st.info("Please check the URL and your internet connection.")

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
st.markdown("Created with Streamlit, Pytubefix, and MoviePy.")
