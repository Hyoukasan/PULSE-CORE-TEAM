import os
from dotenv import load_dotenv

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///pulse_project.db'
    REDIS_HOST = os.getenv('REDIS_HOST')
    REDIS_PORT = os.environ.get('REDIS_PORT', 6379)
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')

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