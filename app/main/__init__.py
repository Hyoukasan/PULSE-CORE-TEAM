import os

from flask import Flask
from dotenv import load_dotenv

from .config import config
from app.src.integrations.db import db
from app.src.integrations.redis_client import init_redis

def create_app(config_name="default"):

    load_dotenv()

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    init_redis(app)


    return app

