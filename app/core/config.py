from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Hackathon API"
    app_version: str = "0.1.0"
    debug: bool = True

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001", "http://localhost:5173"]

    log_level: str = "INFO"

    secret_key: str = "dev-only-change-me"

    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model_agent: str = "openai/gpt-oss-120b"
    groq_model_fast: str = "openai/gpt-oss-20b"
    groq_timeout_s: float = 30.0
    groq_key_cooldown_s: float = 60.0

    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle: int = 300
    db_pool_timeout: int = 30

    database_url: str = "postgresql+psycopg://user:password@localhost:5432/hackathon"

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url


settings = Settings()
