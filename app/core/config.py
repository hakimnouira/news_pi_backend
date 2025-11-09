from pydantic_settings import BaseSettings
from typing import List
import secrets


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"

    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  
    ALGORITHM: str = "HS256"

    # DB
    DATABASE_URL: str = "sqlite:///./app.db"  

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    # First superuser (seed)
    FIRST_SUPERUSER_EMAIL: str = "admin@example.com"
    FIRST_SUPERUSER_PASSWORD: str = "admin"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
