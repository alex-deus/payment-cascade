from django.conf import settings
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from .schema import CustomOpenAPISchemaGenerator


__all__ = ["schema_view"]

schema_view = get_schema_view(
    openapi.Info(title="Payment - API", default_version="1.0.0"),
    settings.BASE_URL,
    public=True,
    permission_classes=[permissions.AllowAny],
    authentication_classes=[],
    generator_class=CustomOpenAPISchemaGenerator,
)
