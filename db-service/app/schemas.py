from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class VideoBase(BaseModel):
    video_id: str
    title: str
    audio_file_path: str
    duration: Optional[float] = None

class VideoCreate(VideoBase):
    pass

class Video(VideoBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True 