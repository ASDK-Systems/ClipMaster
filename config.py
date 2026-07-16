"""
YTAutomation — Application Configuration

Loads settings from environment variables / .env file.
"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration loaded from environment variables."""

    # --- OpenAI ---
    openai_api_key: str = "" # Still kept for optional cloud fallback, but no longer required for STT

    # --- Ollama (local AI for viral clip detection) ---
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "gemma4"

    # --- Gemini (cloud AI for viral clip detection, via OpenAI-compatible endpoint) ---
    use_gemini: bool = True
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_model: str = "gemini-3.1-flash-lite"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ytautomation"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Object Storage ---
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket_name: str = "ytautomation"

    # --- Whop ---
    whop_api_key: str = ""
    whop_webhook_secret: str = ""

    # --- YouTube ---
    youtube_client_secrets_file: str = "client_secrets.json"

    # --- App Settings ---
    max_video_duration_minutes: int = 180
    # Browser to pull YouTube cookies from, to bypass bot-detection (chrome, firefox, edge, brave, etc.)
    # Leave empty to disable. Requires that browser to be closed, or logged into YouTube.
    youtube_cookies_from_browser: str = ""
    max_clips_per_video: int = 10
    downloads_dir: Path = Path("./downloads")
    output_dir: Path = Path("./output")

    # --- FFmpeg ---
    ffmpeg_location: str | None = None

    # --- Model Selection ---
    local_whisper_model: str = "mlx-community/whisper-base-mlx"  # e.g., "mlx-community/whisper-tiny-mlx", etc.
    
    # ollama_model is set above — change it to your preferred local model
    # Popular options: gemma4, llama3.1:8b, llama3.1:70b, mistral, qwen2.5:32b

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    def ensure_dirs(self) -> None:
        """Create required directories if they don't exist."""
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


# Singleton instance
settings = Settings()
