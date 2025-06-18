from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio
import httpx
from .config import get_settings
from .services import AudioTextService
import os

# Get settings
settings = get_settings()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=settings.service_name,
    version=settings.service_version,
    openapi_url=f"{settings.api_prefix}/openapi.json",
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1}
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize service
audio_text_service = AudioTextService()

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": "running",
        "docs_url": f"{settings.api_prefix}/docs",
        "openapi_url": f"{settings.api_prefix}/openapi.json"
    }

@app.get(f"{settings.api_prefix}/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "model_loaded": audio_text_service.whisper_pipeline is not None
    }

@app.post(f"{settings.api_prefix}/process-audio/{{video_id}}")
async def process_audio(video_id: str):
    try:
        if audio_text_service.whisper_pipeline is None:
            logger.error("Whisper model not loaded")
            raise HTTPException(
                status_code=500,
                detail="Whisper model not loaded. Please check the service logs."
            )
            
        logger.info(f"Starting audio processing for video {video_id}")
        
        # Get video details first to validate the video exists
        try:
            video_info = await audio_text_service.get_video_details(video_id)
            if not video_info:
                raise HTTPException(
                    status_code=404,
                    detail=f"Video {video_id} not found in database"
                )
            
            audio_path = video_info.get("audio_file_path")
            if not audio_path:
                raise HTTPException(
                    status_code=404,
                    detail=f"No audio file path found for video {video_id}"
                )
                
            if not os.path.exists(audio_path):
                raise HTTPException(
                    status_code=404,
                    detail=f"Audio file not found at {audio_path}"
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error validating video: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error validating video: {str(e)}"
            )
        
        # Process the audio
        success = await audio_text_service.process_audio(video_id)
        
        if success:
            logger.info(f"Successfully processed audio for video {video_id}")
            return {
                "status": "success",
                "message": f"Audio processed for video {video_id}",
                "video_id": video_id,
                "audio_path": audio_path
            }
        else:
            logger.error(f"Failed to process audio for video {video_id}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process audio for video {video_id}. Check the logs for more details."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
