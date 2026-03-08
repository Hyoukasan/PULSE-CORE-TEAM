import os

from flask import Flask
from dotenv import load_dotenv

from .config import Config
from app.src.integrations.db import db
from app.src.integrations.redis_client import init_redis

def create_app(config_name="default"):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    load_dotenv(".env")


    if not app.config["SECRET_KEY"]:

    db.init_app(app)

    return app

