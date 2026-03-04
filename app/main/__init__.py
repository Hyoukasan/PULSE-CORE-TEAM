import os

from flask import Flask
import logging
from dotenv import load_dotenv
from app.main import config

def create_app(config_name=None):
    app = Flask(__name__)

    load_dotenv(".env")


    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development') # devmode


    return app

