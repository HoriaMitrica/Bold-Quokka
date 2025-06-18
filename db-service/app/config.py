from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Service Configuration
    service_name: str = "db-service"
    service_version: str = "1.0.0"
    
    # API Configuration
    api_prefix: str = "/api/v1"
    
    # Database Configuration
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "videos"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    
    # Service Port
    port: int = 8001
    
    @property
    def database_url(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    class Config:
        env_file = ".env"
        env_prefix = "DB_SERVICE_"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    return Settings() 