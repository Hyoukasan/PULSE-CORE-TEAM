import redis
from flask import current_app
from sqlalchemy.sql.coercions import expect


def init_redis(app):
    
    app.redis_client = redis.Redis(
        host=app.config['REDIS_HOST'],
        port=app.config['REDIS_PORT'],
        db=app.config['REDIS_DB'],
        #password=app.config.get('REDIS_PASSWORD'),
        decode_responses=True
    )

    try:
        app.redis_client.ping()
        app.logger.info("Redis connected")
    except redis.ConnectionError as error:
        app.logger.warning("Connection failed: %s", error)



def get_redis():
    return current_app.redis_client