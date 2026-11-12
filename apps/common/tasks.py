import logging

import sentry_sdk
from celery import Task
from django.db import transaction


__all__ = ["TracedTask"]

logger = logging.getLogger("celery.tasks")


class TracedTask(Task):
    def delay_on_commit(self, *args, **kwargs):
        transaction.on_commit(lambda: self.delay(*args, **kwargs))

    def __call__(self, *args, **kwargs):
        headers: dict = getattr(self.request, "headers", {})
        if headers:
            tx_ctx = sentry_sdk.continue_trace(headers, op="celery.task", name=self.name)
            with sentry_sdk.start_transaction(tx_ctx):
                return self.run(*args, **kwargs)
        else:
            return self.run(*args, **kwargs)
