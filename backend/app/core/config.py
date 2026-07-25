# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Northstar AI Knowledge Assistant"
    app_env: str = "development"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"

    # Database
    database_url: str = "sqlite:///./northstar.db"

    # JWT Authentication
    jwt_secret: str = "change_this_secret_in_production_123!"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()