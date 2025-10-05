from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl


class Settings(BaseSettings):
    DB_URL: str
    CORS_ORIGINS: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
