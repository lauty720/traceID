from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    MAX_UPLOAD_SIZE_MB: int = 10
    UPLOAD_DIR: str = "./uploads"
    TEMP_FILE_TTL_SECONDS: int = 300

    FORCE_DEMO_MODE: bool = False

    GEMINI_API_KEY: str = ""
    AI_DETECTOR_API_KEY: str = ""
    AI_DETECTOR_API_URL: str = ""
    REVERSE_SEARCH_API_KEY: str = ""
    REVERSE_SEARCH_API_URL: str = ""

    RATE_LIMIT: str = "20/minute"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def cors_origins_list(self) -> List[str]:
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        # Allow * for simple deploys (Netlify + Render)
        if "*" in origins:
            return ["*"]
        return origins

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def is_demo_mode(self) -> bool:
        if self.FORCE_DEMO_MODE:
            return True
        # Real mode if at least one analysis API is configured
        # (Gemini alone is not enough for full real analysis)
        has_detector = bool(self.AI_DETECTOR_API_KEY)
        has_reverse = bool(self.REVERSE_SEARCH_API_KEY)
        return not (has_detector or has_reverse)


settings = Settings()