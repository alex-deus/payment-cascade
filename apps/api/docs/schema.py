from drf_yasg import openapi
from drf_yasg.generators import OpenAPISchemaGenerator


__all__ = ["MERCHANT_PARAMS", "SIGNATURE_PARAMS", "CREATED_PARAMS", "CustomOpenAPISchemaGenerator"]


MERCHANT_PARAMS = [
    openapi.Parameter(
        "merchant", openapi.IN_HEADER, "Merchant UUID", True, type=openapi.TYPE_STRING, format=openapi.FORMAT_UUID
    )
]

SIGNATURE_PARAMS = [
    openapi.Parameter("signature", openapi.IN_HEADER, "Signature of data", True, type=openapi.TYPE_STRING)
]

CREATED_PARAMS = [
    openapi.Parameter("created", openapi.IN_QUERY, "Created datetime in ISO format", True, type=openapi.TYPE_STRING)
]


class CustomOpenAPISchemaGenerator(OpenAPISchemaGenerator):
    def get_schema(self, request=None, public=False):
        swagger = super().get_schema(request, public)

        # swagger.tags = [
        #     {"name": "merchant", "description": "Merchant API"},
        #     {"name": "balance", "description": "Balance API"},
        #     {"name": "order", "description": "Order API"},
        #     {"name": "payout", "description": "Payout API"},
        #     {"name": "service", "description": "Service API"},
        # ]

        return swagger
