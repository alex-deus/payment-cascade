import logging

from celery import shared_task
from django.db import Error as DjangoDBError
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from apps.common.tasks import TracedTask


__all__ = ["flush_expired_jwt_tokens"]

logger = logging.getLogger("celery.tasks")


@shared_task(
    bind=True,
    base=TracedTask,
    max_retries=3,
    retry_backoff=True,
    autoretry_for=(DjangoDBError,),
)
def flush_expired_jwt_tokens(self) -> int:
    deleted_count, _ = OutstandingToken.objects.filter(expires_at__lt=timezone.now()).delete()

    logger.info(f"Flushed {deleted_count} expired JWT outstanding tokens")

    return deleted_count
