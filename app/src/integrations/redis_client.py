import redis
from flask import current_app


def init_redis(app):
    redis_host = app.config.get('REDIS_HOST')
    if not redis_host:
        app.logger.warning("REDIS_HOST not set, Redis disabled")
        app.redis_client = None
        return
    
    password = app.config.get('REDIS_PASSWORD')
    app.redis_client = redis.Redis(
        host=redis_host,
        port=app.config['REDIS_PORT'],
        password=password if password else None,
        decode_responses=True,
        socket_connect_timeout=2,
    )

    try:
        app.redis_client.ping()
        app.logger.info("Redis connected")
    except (redis.exceptions.ConnectionError, ConnectionRefusedError, OSError) as error:
        app.logger.warning("Redis connection unavailable, continuing without Redis: %s", error)
        app.redis_client = None


def get_redis():
    client = current_app.redis_client
    if client is None:
        raise RuntimeError("Redis not configured")
    return client