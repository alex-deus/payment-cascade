from django.http import HttpResponse
from django.views import View


__all__ = ["HealthCheckView"]


class HealthCheckView(View):
    def get(self, request, *args, **kwargs) -> HttpResponse:
        return HttpResponse("OK")
