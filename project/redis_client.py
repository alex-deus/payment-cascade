import redis
from django.conf import settings


__all__ = ["redis_client"]

redis_client: redis.Redis = redis.from_url(settings.REDIS_DSN, decode_responses=True)
