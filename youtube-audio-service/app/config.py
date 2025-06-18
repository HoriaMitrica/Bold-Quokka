from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path

class Settings(BaseSettings):
    # Service Configuration
    service_name: str = "youtube-audio-service"
    service_version: str = "1.0.0"
    
    # API Configuration
    api_prefix: str = "/api/v1"
    
    # Service URLs
    db_service_url: str = "http://localhost:8001"
    
    # File Storage Configuration
    audio_dir: Path = Path("downloaded_audio")
    
    # Service Port
    port: int = 8003
    
    class Config:
        env_file = ".env"
        env_prefix = "YOUTUBE_AUDIO_SERVICE_"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    return Settings() 