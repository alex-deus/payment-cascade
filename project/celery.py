import os
from datetime import timedelta

from celery import Celery, signals
from django.apps import apps


__all__ = ["app"]

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

app = Celery("project", namespace="CELERY")
app.config_from_object("django.conf:settings")
app.autodiscover_tasks(lambda: [cfg.name for cfg in apps.get_app_configs()])
app.conf.worker_cancel_long_running_tasks_on_connection_loss = True

app.conf.beat_schedule = {
    "user.flush_expired_jwt_tokens": {
        "task": "apps.users.tasks.flush_expired_jwt_tokens",
        "schedule": timedelta(minutes=20),
    },
    "payment.deactivate_providers": {
        "task": "apps.payment.tasks.deactivate_providers",
        "schedule": timedelta(minutes=5),
    },
    "payment.mark_stale_attempts_as_timed_out": {
        "task": "apps.payment.tasks.mark_stale_attempts_as_timed_out",
        "schedule": timedelta(minutes=5),
    },
    "payment.resume_failed_payments": {
        "task": "apps.payment.tasks.resume_failed_payments",
        "schedule": timedelta(minutes=1),
    },
}


@signals.celeryd_init.connect
def celeryd_init_sentry(**kwargs) -> None:
    from . import sentry

    sentry.initialize_sentry()


@signals.beat_init.connect
def beat_init_sentry(**kwargs) -> None:
    from . import sentry

    sentry.initialize_sentry()
