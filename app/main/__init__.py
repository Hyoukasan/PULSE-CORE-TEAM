from flask import Flask
import logging
from dotenv import dotenv_values
from app.main import config

def create_app(config_name = None):
    app = Flask(__name__)

    if config_name is None:
        config_name = "default"


    return app

env = dotenv_values(".env")
