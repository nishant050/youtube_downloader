# First, you need to install the pytubefix library.
# You can do this by running the following command in your terminal:
# pip install --upgrade pytubefix

from pytubefix import YouTube
from pytubefix.exceptions import PytubeFixError
from urllib.error import HTTPError

def download_video(url):
    """
    Downloads a YouTube video from the given URL in the highest resolution.

    Args:
        url (str): The URL of the YouTube video.
    """
    try:
        # Create a YouTube object
        yt = YouTube(url)

        # Get the video title
        print(f"Title: {yt.title}")
        print("Fetching streams...")

        # Get the highest resolution stream
        # .get_highest_resolution() downloads a progressive stream (video + audio)
        stream = yt.streams.get_highest_resolution()

        if stream:
            print(f"Found highest resolution stream: {stream.resolution}")
            print("Downloading...")

            # Download the video
            # You can specify an output path, otherwise it will be the current directory
            stream.download()

            print("Download completed successfully!")
        else:
            print("No progressive stream with video and audio found.")
            print("Trying to download best video and audio streams separately...")
            
            # Fallback for streams that have separate video and audio (DASH)
            video_stream = yt.streams.filter(adaptive=True, file_extension='mp4').order_by('resolution').desc().first()
            audio_stream = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc().first()

            if video_stream and audio_stream:
                print(f"Found video stream: {video_stream.resolution}")
                print(f"Found audio stream: {audio_stream.abr}")
                print("Downloading video...")
                video_file = video_stream.download(filename_prefix='video_')
                print("Downloading audio...")
                audio_file = audio_stream.download(filename_prefix='audio_')
                print("\nDownload completed.")
                print("NOTE: You may need to merge the separate video and audio files using a tool like FFmpeg.")
            else:
                print("Could not find suitable video or audio streams to download.")

    except HTTPError as e:
        print(f"\nA network error occurred: {e}")
        print("This might be due to an invalid URL, an age-restricted video, or a change in the YouTube API.")
        print("Please ensure the URL is correct and try updating pytubefix with: pip install --upgrade pytubefix")
    except PytubeFixError as e:
        print(f"\nAn error occurred with pytubefix: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        print("Please check the URL and your internet connection.")

if __name__ == "__main__":
    # Get the YouTube video URL from the user
    video_url = input("Enter the YouTube video URL: ")
    
    if video_url:
        download_video(video_url)
    else:
        print("No URL provided. Exiting.")
