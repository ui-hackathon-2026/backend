from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Hackathon API"
    app_version: str = "0.1.0"
    debug: bool = True

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]


settings = Settings()
