import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DISCORD_TOKEN: str
    MONGO_URI: str

    class Config:
        env_file = ".env"

config = Settings()