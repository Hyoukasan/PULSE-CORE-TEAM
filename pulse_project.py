from flask import Flask
import logging
from dotenv import dotenv_values
from app.src.config import setConfig

env = dotenv_values(".env")

app = Flask(__name__)

logging.basicConfig(filename='app.log', level=logging.ERROR, 
                    format='%(asctime)s %(levelname)s: %(message)s')

setConfig(app, env)

print(f"База подключена: {app.config['SQLALCHEMY_DATABASE_URI']}")
