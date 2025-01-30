# from pathlib import Path
from dotenv import find_dotenv
from pydantic_settings import BaseSettings

# PROJECT_ROOT = Path(__file__).parent.parent


class Settings(BaseSettings):
    """Settings for the FastAPI application."""

    model_config = {
        "env_file": find_dotenv(),
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }
    CONFIG_DIR: str = "../../config"

    OPENAI_API_KEY: str
    OPENAI_API_VERSION: str

    MONGODB_URI: str
    GOOGLE_CREDENTIALS_PATH: str
    GOOGLE_SPREADSHEET_ID: str
    GOOGLE_CLOUD_PROJECT_ID: str


SETTINGS = Settings()
