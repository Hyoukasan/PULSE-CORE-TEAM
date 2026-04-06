import os
from dotenv import load_dotenv
load_dotenv()
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
DEFAULT_DB_PATH = os.path.join(INSTANCE_DIR, "pulse_project.db")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}"
    )
    SHEETS_SYNC_API_KEY = os.environ.get("SHEETS_SYNC_API_KEY")
    REDIS_HOST = os.getenv("REDIS_HOST")
    REDIS_PORT = os.environ.get("REDIS_PORT", 6379)
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

class TestingConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///pulse_test.db'


config = {
    "development" : DevelopmentConfig,
    "production" : ProductionConfig,
    "testing" : TestingConfig,
    "default" : DevelopmentConfig
}