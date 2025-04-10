from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import logging
from uuid import UUID

from . import models, schemas
from .database import engine, get_db

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Database Service")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.post("/videos/", response_model=schemas.Video)
def create_video(video: schemas.VideoCreate, db: Session = Depends(get_db)):
    db_video = models.Video(**video.model_dump())
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    return db_video

@app.get("/videos/", response_model=List[schemas.Video])
def read_videos(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    videos = db.query(models.Video).offset(skip).limit(limit).all()
    return videos

@app.get("/videos/{video_id}", response_model=schemas.Video)
def read_video(video_id: str, db: Session = Depends(get_db)):
    video = db.query(models.Video).filter(models.Video.video_id == video_id).first()
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@app.patch("/videos/{video_id}", response_model=schemas.Video)
def update_video(video_id: str, video_update: schemas.VideoUpdate, db: Session = Depends(get_db)):
    db_video = db.query(models.Video).filter(models.Video.video_id == video_id).first()
    if db_video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    
    for key, value in video_update.model_dump(exclude_unset=True).items():
        setattr(db_video, key, value)
    
    db.commit()
    db.refresh(db_video)
    return db_video

@app.delete("/videos/{video_id}")
def delete_video(video_id: str, db: Session = Depends(get_db)):
    video = db.query(models.Video).filter(models.Video.video_id == video_id).first()
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    db.delete(video)
    db.commit()
    return {"status": "success", "message": "Video deleted"}

# Text Content endpoints
@app.post("/text-contents/", response_model=schemas.TextContent)
def create_text_content(text_content: schemas.TextContentCreate, db: Session = Depends(get_db)):
    db_text_content = models.TextContent(**text_content.model_dump())
    db.add(db_text_content)
    db.commit()
    db.refresh(db_text_content)
    return db_text_content

@app.get("/text-contents/", response_model=List[schemas.TextContent])
def read_text_contents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    text_contents = db.query(models.TextContent).offset(skip).limit(limit).all()
    return text_contents

@app.get("/text-contents/{text_content_id}", response_model=schemas.TextContent)
def read_text_content(text_content_id: UUID, db: Session = Depends(get_db)):
    text_content = db.query(models.TextContent).filter(models.TextContent.id == text_content_id).first()
    if text_content is None:
        raise HTTPException(status_code=404, detail="Text content not found")
    return text_content

@app.get("/videos/not-text/", response_model=List[schemas.Video])
def read_videos_not_text(db: Session = Depends(get_db)):
    videos = db.query(models.Video).filter(models.Video.text_status == "NOT_TEXT").all()
    return videos 