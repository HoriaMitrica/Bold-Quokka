from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from uuid import UUID
from enum import Enum

class TextStatus(str, Enum):
    NOT_TEXT = "NOT_TEXT"
    PROCESSING = "PROCESSING"
    TEXT = "TEXT"

class VideoBase(BaseModel):
    video_id: str
    title: str
    audio_file_path: str
    duration: Optional[float] = None
    text_status: TextStatus = TextStatus.NOT_TEXT

class VideoCreate(VideoBase):
    pass

class VideoUpdate(BaseModel):
    title: Optional[str] = None
    audio_file_path: Optional[str] = None
    duration: Optional[float] = None
    text_status: Optional[TextStatus] = None

class Video(VideoBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class TextContentBase(BaseModel):
    video_id: str
    name: str
    text_file_path: str

class TextContentCreate(TextContentBase):
    id: Optional[UUID] = None

class TextContent(BaseModel):
    id: Optional[UUID] = None
    video_id: str
    name: str
    text_file_path: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True 