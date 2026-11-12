import logging
from functools import partial, wraps
from time import sleep

from django.conf import settings
from django.db import OperationalError, connections
from psycopg2 import OperationalError as Psycopg2OperationalError


__all__ = ["get_boto3_client", "with_db_reconnect"]


logger = logging.getLogger("django.request")


def get_boto3_client(
    service,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
    endpoint_url=settings.AWS_S3_ENDPOINT_URL,
    **kwargs,
):
    import boto3

    if not getattr(get_boto3_client, "cache", None):
        get_boto3_client.cache = {}

    if service not in get_boto3_client.cache:
        get_boto3_client.cache[service] = boto3.client(
            service,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
            endpoint_url=endpoint_url,
            **kwargs,
        )

    return get_boto3_client.cache[service]


def with_db_reconnect(func=None, *, max_retries=10, retry_delay=1):
    if func is None:
        return partial(with_db_reconnect, max_retries=max_retries, retry_delay=retry_delay)

    @wraps(func)
    def wrapper(*args, **kwargs):
        attempt = 0
        while attempt < max_retries:
            try:
                return func(*args, **kwargs)
            except (OperationalError, Psycopg2OperationalError) as e:
                if "server closed the connection" in str(e).lower() or "connection timed out" in str(e).lower():
                    logger.warning(f"DB connection has lost. attempt={attempt}")

                    connections.close_all()
                    sleep(retry_delay)
                    attempt += 1
                else:
                    raise

        raise Exception(f"Could not connect to db after attempt={attempt}")

    return wrapper
