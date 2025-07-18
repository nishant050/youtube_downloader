# To run this app, you need to install streamlit and pytubefix:
# pip install streamlit pytubefix
#
# Then, save this code as a Python file (e.g., app.py) and run from your terminal:
# streamlit run app.py

import streamlit as st
from pytubefix import YouTube
from pytubefix.exceptions import PytubeFixError
from urllib.error import HTTPError
import os
import time

def download_video(url, progress_bar, status_text):
    """
    Downloads a YouTube video from the given URL and updates the Streamlit UI.

    Args:
        url (str): The URL of the YouTube video.
        progress_bar (st.progress): Streamlit progress bar object.
        status_text (st.empty): Streamlit empty object for status text.
    """
    try:
        # Create a 'downloads' directory if it doesn't exist
        if not os.path.exists('downloads'):
            os.makedirs('downloads')

        # --- Progress Callback ---
        def on_progress(stream, chunk, bytes_remaining):
            total_size = stream.filesize
            bytes_downloaded = total_size - bytes_remaining
            percentage = (bytes_downloaded / total_size) * 100
            progress_bar.progress(int(percentage))
            status_text.text(f"Downloading... {int(percentage)}%")

        # --- YouTube Object ---
        yt = YouTube(url, on_progress_callback=on_progress)

        status_text.text(f"Fetching video: {yt.title}")
        st.write(f"**Title:** {yt.title}")

        # --- Stream Selection ---
        stream = yt.streams.get_highest_resolution()

        if stream:
            status_text.text(f"Found stream: {stream.resolution}. Starting download...")
            time.sleep(1) # Give user time to read the status
            
            # --- Download ---
            # We specify the output path and a clean filename
            output_path = 'downloads'
            filename = f"{yt.title}.mp4".replace("/", "-").replace("\\", "-") # Sanitize filename
            filepath = stream.download(output_path=output_path, filename=filename)
            
            progress_bar.progress(100)
            status_text.text("Download completed successfully!")
            st.success("Download complete!")

            # --- Provide Download Link ---
            with open(filepath, "rb") as file:
                st.download_button(
                    label="Download Video File",
                    data=file,
                    file_name=os.path.basename(filepath),
                    mime="video/mp4"
                )
            
            # Clean up the downloaded file on the server after some time
            # In a real-world scenario, you might have a better cleanup strategy
            # For this example, we'll just leave it in the 'downloads' folder.

        else:
            st.warning("No progressive stream with video and audio found.")
            # You could add logic here to download separate streams if needed

    except HTTPError as e:
        st.error(f"Network Error: {e}")
        st.warning("This could be an invalid URL, an age-restricted video, or a temporary YouTube issue.")
    except PytubeFixError as e:
        st.error(f"PytubeFix Error: {e}")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        st.info("Please check the URL and your internet connection.")

# --- Streamlit App UI ---
st.set_page_config(page_title="YouTube Video Downloader", layout="centered")
st.title("🎬 YouTube Video Downloader")
st.write("Paste a YouTube video URL below and click 'Download' to get the highest resolution video.")

# --- URL Input ---
video_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")

# --- Download Button and Logic ---
if st.button("Download"):
    if video_url:
        with st.spinner('Preparing download...'):
            # UI elements for feedback
            progress_bar = st.progress(0)
            status_text = st.empty()
            try:
                download_video(video_url, progress_bar, status_text)
            except Exception as e:
                st.error(f"Failed to process download: {e}")

    else:
        st.warning("Please enter a YouTube URL.")

st.markdown("---")
st.markdown("Created with Streamlit and Pytubefix.")
