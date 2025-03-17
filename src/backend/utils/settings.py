# from pathlib import Path
from dotenv import find_dotenv, load_dotenv
import time
from pymongo.errors import ConfigurationError
from pydantic_settings import BaseSettings

load_dotenv(find_dotenv(), override=True)


class Settings(BaseSettings):
    """Settings for the FastAPI application."""

    model_config = {
        "env_file": find_dotenv(),
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }
    CONFIG_DIR: str = "../../config"

    OPENAI_API_KEY: str

    GOOGLE_CREDENTIALS_PATH: str
    GOOGLE_SPREADSHEET_ID: str
    GOOGLE_CLOUD_PROJECT_ID: str
    MONGODB_URI: str
    # MONGODB_USERNAME: str
    # MONGODB_PASSWORD: str


SETTINGS = Settings()
