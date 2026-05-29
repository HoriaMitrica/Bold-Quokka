from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, HttpUrl
import yt_dlp
import os
from pathlib import Path
import logging
import httpx
import json
from dotenv import load_dotenv
from .config import get_settings
from prometheus_fastapi_instrumentator import Instrumentator

# Load environment variables from .env file
load_dotenv()

# Get settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title=settings.service_name,
    version=settings.service_version,
    openapi_url=f"{settings.api_prefix}/openapi.json",
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
)
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create directories for storing audio files
AUDIO_DIR = Path(settings.audio_dir)
AUDIO_DIR.mkdir(exist_ok=True)

class YouTubeRequest(BaseModel):
    url: HttpUrl

@app.get("/")
async def root():
    return {"message": "Welcome to the Microservice API"}

@app.get(f"{settings.api_prefix}/health")
async def health_check():
    db_health_url = f"{settings.db_service_url}{settings.api_prefix}/health"
    db_healthy = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(db_health_url)
            db_healthy = response.status_code == 200
    except Exception:
        db_healthy = False

    status = "healthy" if db_healthy else "degraded"
    return {
        "status": status,
        "database_service_reachable": db_healthy,
        "audio_dir": str(AUDIO_DIR),
    }

@app.post(f"{settings.api_prefix}/extract-audio")
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

                # Create video record in database
                db_service_url = settings.db_service_url
                video_data = {
                    "video_id": video_id,
                    "title": info.get('title', 'Unknown Title'),
                    "audio_file_path": str(audio_file),
                    "duration": info.get('duration'),
                    "text_status": "NOT_TEXT"
                }

                logger.info(f"Attempting to create database record with data: {json.dumps(video_data, indent=2)}")
                logger.info(f"Database service URL: {db_service_url}{settings.api_prefix}/videos")

                async with httpx.AsyncClient() as client:
                    try:
                        response = await client.post(
                            f"{db_service_url}{settings.api_prefix}/videos",
                            json=video_data,
                            timeout=30.0  # Add timeout
                        )
                        logger.info(f"Database service response status: {response.status_code}")
                        logger.info(f"Database service response body: {response.text}")
                        
                        response.raise_for_status()
                        db_record = response.json()
                        logger.info(f"Successfully created database record: {json.dumps(db_record, indent=2)}")
                    except httpx.HTTPError as e:
                        logger.error(f"Failed to create database record. Error: {str(e)}")
                        logger.error(f"Response status: {e.response.status_code if hasattr(e, 'response') else 'N/A'}")
                        logger.error(f"Response body: {e.response.text if hasattr(e, 'response') else 'N/A'}")
                        # Continue even if database operation fails
                        # The file is still saved locally

                logger.info(f"Successfully extracted audio for video ID: {video_id}")
                return {
                    "status": "success",
                    "video_id": video_id,
                    "title": info.get('title', 'Unknown Title'),
                    "audio_file": str(audio_file),
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