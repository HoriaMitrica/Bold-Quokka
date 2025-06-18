from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path

class Settings(BaseSettings):
    # Service Configuration
    service_name: str = "audio-text-service"
    service_version: str = "1.0.0"
    
    # API Configuration
    api_prefix: str = "/api/v1"
    
    # Service URLs
    db_service_url: str = "http://localhost:8001"
    
    # File Storage Configuration
    audio_dir: Path = Path("downloaded_audio")
    text_dir: Path = Path("downloaded_text")
    
    # Hugging Face Configuration
    hf_token: str = ""
    
    # Service Port
    port: int = 8002
    
    class Config:
        env_file = ".env"
        env_prefix = "AUDIO_TEXT_SERVICE_"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    return Settings() 