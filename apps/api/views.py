from django.http import HttpResponse
from rest_framework.views import APIView


__all__ = ["HealthView"]


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request) -> HttpResponse:
        return HttpResponse("OK", content_type="text/plain")
