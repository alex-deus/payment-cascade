import logging

from django.core.handlers.wsgi import WSGIRequest
from django.db import DatabaseError, close_old_connections
from django.middleware.locale import LocaleMiddleware
from django.utils.deprecation import MiddlewareMixin
from ipware import get_client_ip


__all__ = ["DjangoLoggingMiddleware", "CloseOldDbConnectionsMiddleware", "UserLocaleMiddleware"]

logger = logging.getLogger("django.request")


class DjangoLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: WSGIRequest):
        response = self.get_response(request)

        client_ip, _ = get_client_ip(request)
        extra = {
            "client_ip": client_ip,
            "status_code": response.status_code,
            "method": request.method.lower(),
            "path": request.path or request.path_info,
            "user_id": request.user.pk if hasattr(request, "user") and request.user.is_authenticated else None,
        }

        # message = f"[{response.status_code}] {request.method} {request.build_absolute_uri()}"
        logger.info("", extra=extra)

        return response


class CloseOldDbConnectionsMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if isinstance(exception, DatabaseError):
            close_old_connections()


class UserLocaleMiddleware(LocaleMiddleware):
    def process_request(self, request):
        super().process_request(request)

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return
