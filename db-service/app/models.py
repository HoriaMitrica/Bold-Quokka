from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum
from .database import Base

class TextStatus(enum.Enum):
    NOT_TEXT = "NOT_TEXT"
    PROCESSING = "PROCESSING"
    TEXT = "TEXT"

class Video(Base):
    __tablename__ = "videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(String, unique=True, index=True)
    title = Column(String)
    audio_file_path = Column(String)
    duration = Column(Float)
    text_status = Column(Enum(TextStatus), default=TextStatus.NOT_TEXT)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TextContent(Base):
    __tablename__ = "text_contents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(String, index=True)
    name = Column(String)
    text_file_path = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())