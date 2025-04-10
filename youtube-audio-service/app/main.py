from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
import yt_dlp
import os
from pathlib import Path
import logging
import httpx
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="YouTube Audio Extractor Service")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create directories for storing audio files
AUDIO_DIR = Path("/app/audio")
LOCAL_AUDIO_DIR = Path("./downloaded_audio")
AUDIO_DIR.mkdir(exist_ok=True)
LOCAL_AUDIO_DIR.mkdir(exist_ok=True)

class YouTubeRequest(BaseModel):
    url: HttpUrl

@app.get("/")
async def root():
    return {"message": "Welcome to the Microservice API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/extract-audio")
async def extract_audio(request: YouTubeRequest):
    try:
        # Configure yt-dlp options with more robust settings
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'outtmpl': str(AUDIO_DIR / '%(id)s.%(ext)s'),
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'no_warnings': True,
            'quiet': False,
            'extract_flat': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        }

        # Download and extract audio
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                logger.info(f"Attempting to extract audio from URL: {request.url}")
                info = ydl.extract_info(str(request.url), download=True)
                
                if info is None:
                    logger.error("Failed to extract video information")
                    raise HTTPException(status_code=400, detail="Could not extract video information")
                
                video_id = info.get('id', 'unknown')
                audio_file = AUDIO_DIR / f"{video_id}.wav"
                
                if not audio_file.exists():
                    logger.error(f"Audio file was not created: {audio_file}")
                    raise HTTPException(status_code=500, detail="Audio file was not created successfully")

                # Copy the file to local directory
                local_audio_file = LOCAL_AUDIO_DIR / f"{video_id}.wav"
                with open(audio_file, 'rb') as src, open(local_audio_file, 'wb') as dst:
                    dst.write(src.read())

                # Create video record in database
                db_service_url = os.getenv("DB_SERVICE_URL", "http://db-service:8001")
                video_data = {
                    "video_id": video_id,
                    "name": info.get('title', 'Unknown Title'),
                    "audio_file_path": str(local_audio_file),
                    "duration": info.get('duration')
                }

                async with httpx.AsyncClient() as client:
                    try:
                        response = await client.post(
                            f"{db_service_url}/videos/",
                            json=video_data
                        )
                        response.raise_for_status()
                        db_record = response.json()
                        logger.info(f"Created database record: {db_record}")
                    except httpx.HTTPError as e:
                        logger.error(f"Failed to create database record: {str(e)}")
                        # Continue even if database operation fails
                        # The file is still saved locally

                logger.info(f"Successfully extracted audio for video ID: {video_id}")
                return {
                    "status": "success",
                    "video_id": video_id,
                    "name": info.get('title', 'Unknown Title'),
                    "audio_file": str(local_audio_file),
                    "duration": info.get('duration'),
                }
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                logger.error(f"YouTube download error: {error_msg}")
                
                if "Sign in to confirm you're not a bot" in error_msg:
                    raise HTTPException(
                        status_code=403,
                        detail="YouTube requires verification. Please try again later or use a different video."
                    )
                elif "Failed to extract any player response" in error_msg:
                    raise HTTPException(
                        status_code=500,
                        detail="YouTube player extraction failed. This might be due to YouTube changes or network issues. Please try again later."
                    )
                raise HTTPException(status_code=500, detail=f"YouTube download error: {error_msg}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 