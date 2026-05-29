from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
import logging
from uuid import UUID
from prometheus_fastapi_instrumentator import Instrumentator

from . import models, schemas
from .database import engine, get_db
from .config import get_settings

# Get settings
settings = get_settings()

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.service_name,
    version=settings.service_version,
    openapi_url=f"/openapi.json",
    docs_url=f"/docs",
    redoc_url=f"/redoc"
)
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.get(f"{settings.api_prefix}/")
async def root():
    return {"message": "Welcome to the Database Service API"}

@app.get(f"{settings.api_prefix}/health")
async def health_check():
    db = None
    try:
        db = next(get_db())
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database_connected": True,
            "api_prefix": settings.api_prefix,
        }
    except Exception as e:
        return {"status": "unhealthy", "database_connected": False, "error": str(e)}
    finally:
        if db is not None:
            db.close()

@app.post(f"{settings.api_prefix}/videos", response_model=schemas.Video)
def create_video(video: schemas.VideoCreate, db: Session = Depends(get_db)):
    try:
        logger.info(f"Creating video record with data: {video.model_dump()}")
        db_video = models.Video(**video.model_dump())
        db.add(db_video)
        db.commit()
        db.refresh(db_video)
        logger.info(f"Successfully created video record: {db_video.id}")
        return db_video
    except Exception as e:
        logger.error(f"Error creating video record: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create video record: {str(e)}"
        )

@app.get(f"{settings.api_prefix}/videos", response_model=list[schemas.Video])
def get_videos(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    videos = db.query(models.Video).offset(skip).limit(limit).all()
    return videos

@app.get(f"{settings.api_prefix}/videos/{{video_id}}", response_model=schemas.Video)
def get_video(video_id: str, db: Session = Depends(get_db)):
    video = db.query(models.Video).filter(models.Video.video_id == video_id).first()
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@app.patch(f"{settings.api_prefix}/videos/{{video_id}}", response_model=schemas.Video)
def update_video(video_id: str, video_update: schemas.VideoUpdate, db: Session = Depends(get_db)):
    try:
        logger.info(f"Updating video {video_id} with data: {video_update.model_dump(exclude_unset=True)}")
        db_video = db.query(models.Video).filter(models.Video.video_id == video_id).first()
        if db_video is None:
            raise HTTPException(status_code=404, detail="Video not found")
        
        update_data = video_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_video, key, value)
        
        db.commit()
        db.refresh(db_video)
        logger.info(f"Successfully updated video {video_id}")
        return db_video
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating video {video_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update video: {str(e)}"
        )

@app.delete(f"{settings.api_prefix}/videos/{{video_id}}")
def delete_video(video_id: str, db: Session = Depends(get_db)):
    video = db.query(models.Video).filter(models.Video.video_id == video_id).first()
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    db.delete(video)
    db.commit()
    return {"status": "success", "message": "Video deleted"}

# Text Content endpoints
@app.post(f"{settings.api_prefix}/text-contents/", response_model=schemas.TextContent)
def create_text_content(text_content: schemas.TextContentCreate, db: Session = Depends(get_db)):
    db_text_content = models.TextContent(**text_content.model_dump())
    db.add(db_text_content)
    db.commit()
    db.refresh(db_text_content)
    return db_text_content

@app.get(f"{settings.api_prefix}/text-contents/", response_model=List[schemas.TextContent])
def read_text_contents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    text_contents = db.query(models.TextContent).offset(skip).limit(limit).all()
    return text_contents

@app.get(f"{settings.api_prefix}/text-contents/{{text_content_id}}", response_model=schemas.TextContent)
def read_text_content(text_content_id: UUID, db: Session = Depends(get_db)):
    text_content = db.query(models.TextContent).filter(models.TextContent.id == text_content_id).first()
    if text_content is None:
        raise HTTPException(status_code=404, detail="Text content not found")
    return text_content

@app.get(f"{settings.api_prefix}/text-contents/by-video/{{video_id}}", response_model=schemas.TextContent)
def read_text_content_by_video_id(video_id: str, db: Session = Depends(get_db)):
    text_content = db.query(models.TextContent).filter(models.TextContent.video_id == video_id).first()
    if text_content is None:
        raise HTTPException(status_code=404, detail="Text content not found")
    return text_content

@app.get(f"{settings.api_prefix}/videos/not-text/", response_model=List[schemas.Video])
def read_videos_not_text(db: Session = Depends(get_db)):
    videos = db.query(models.Video).filter(models.Video.text_status == "NOT_TEXT").all()
    return videos 