__all__ = ["initialize_sentry"]


def before_send(event, hint) -> None:
    url: str | None = event.get("request", {}).get("url")
    if url and url.startswith("/api/v1/health"):
        return

    if event.get("transaction", "") == "event.django":
        return

    user = event.get("user", {})

    if "email" in user:
        user.pop("email")
    if "username" in user:
        user.pop("username")

    event["user"] = user

    return event


def initialize_sentry() -> None:
    import sentry_sdk
    from django.conf import settings
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        auto_enabling_integrations=False,
        integrations=[
            DjangoIntegration(middleware_spans=False),
            CeleryIntegration(monitor_beat_tasks=True),
            LoggingIntegration(),
        ],
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        profiles_sample_rate=1.0,
        send_default_pii=settings.SENTRY_SEND_DEFAULT_PII,
        environment=settings.ROLE,
        release=settings.TAG,
        before_send=before_send,
    )
