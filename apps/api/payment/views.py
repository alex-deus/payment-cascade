import logging

from django.conf import settings
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from django_essentials_kit.rest_framework.views import SerializerViewSetMixin, generate_filter_parameters
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import exceptions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payment import models
from apps.payment.provider.base import (
    CallbackAuthenticationError,
    CallbackPayloadError,
    CallbackUnsupportedError,
    PaymentStatus,
)
from apps.payment.tasks import finalize_attempt, schedule_payment
from . import filters, serializers


__all__ = ["PaymentViewSet", "ProvidersViewSet", "ProviderCallbackView"]

logger = logging.getLogger("django.request")


class PaymentViewSet(SerializerViewSetMixin, viewsets.ModelViewSet):
    filterset_class = filters.PaymentFilter
    search_fields = ["id"]
    ordering_fields = ["created", "updated", "status"]
    filter_backends = [OrderingFilter, SearchFilter, DjangoFilterBackend]
    serializer_class_map = {
        "create": serializers.PaymentCreateSerializer,
        "list": serializers.PaymentListSerializer,
        "retrieve": serializers.PaymentRetrieveSerializer,
    }
    http_method_names = ["get", "post"]

    def get_queryset(self) -> QuerySet[models.Payment]:
        queryset: QuerySet[models.Payment] = models.Payment.objects.filter(user=self.request.user).select_related(
            "user"
        )

        return queryset

    @swagger_auto_schema(
        request_body=serializers.PaymentCreateSerializer(),
        manual_parameters=[
            openapi.Parameter(
                settings.IDEMPOTENCY_KEY_HEADER,
                openapi.IN_HEADER,
                type=openapi.TYPE_STRING,
                required=False,
                description=_("Idempotency key to prevent request duplication."),
            ),
        ],
        responses={
            status.HTTP_200_OK: serializers.PaymentRetrieveSerializer(),
            status.HTTP_201_CREATED: serializers.PaymentRetrieveSerializer(),
        },
    )
    def create(self, request: Request, *args, **kwargs) -> Response:
        data = request.data.copy()
        data["idempotency_key"] = self.request.headers.get(settings.IDEMPOTENCY_KEY_HEADER)

        serializer = self.get_serializer(data=data, context={"request": request})

        serializer.is_valid(raise_exception=True)
        instance, is_created = self.perform_create(serializer)  # type: models.Payment, bool

        if is_created:
            ...

        status_code = status.HTTP_201_CREATED if is_created else status.HTTP_202_ACCEPTED
        headers = self.get_success_headers(serializer.data)

        serializer = serializers.PaymentRetrieveSerializer(instance=serializer.instance)

        return Response(serializer.data, status_code, headers=headers)

    def perform_create(self, serializer: serializers.PaymentCreateSerializer) -> tuple[models.Payment, bool]:
        idempotency_key: str = serializer.data.pop("idempotency_key")
        instance, is_created = models.Payment.objects.get_or_create(
            user=self.request.user,
            idempotency_key=idempotency_key,
            defaults=serializer.data,
        )

        return instance, is_created

    @swagger_auto_schema(
        responses={status.HTTP_200_OK: serializers.PaymentListSerializer()},
        manual_parameters=generate_filter_parameters(filterset_class, ordering_fields),
    )
    def list(self, request: Request, *args, **kwargs) -> Response:
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(responses={status.HTTP_200_OK: serializers.PaymentRetrieveSerializer()})
    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_name="cancellation", url_path="cancellation")
    def cancel(self, request, pk=None) -> Response:
        raise exceptions.ValidationError(detail=_("Method is still not created"))

    @action(detail=True, methods=["post"], url_name="refund", url_path="refund")
    def refund(self, request, pk=None) -> Response:
        raise exceptions.ValidationError(detail=_("Method is still not created"))


class ProvidersViewSet(viewsets.ReadOnlyModelViewSet):
    filterset_class = filters.PaymentFilter
    search_fields = ["id", "name"]
    ordering_fields = ["is_active", "status"]
    filter_backends = [OrderingFilter, SearchFilter, DjangoFilterBackend]
    serializer_class_map = {
        "list": serializers.ProviderListSerializer,
        "retrieve": serializers.ProviderRetrieveSerializer,
    }


class ProviderCallbackView(APIView):
    """Приём итогового статуса платежа от провайдера.

    Без JWT: проверку подлинности и разбор выполняет реализация провайдера.
    """

    authentication_classes = []
    permission_classes = []
    throttle_classes = []

    @swagger_auto_schema(auto_schema=None)
    def post(self, request: Request, slug: str) -> Response:
        provider = models.Provider.objects.filter(slug=slug).first()
        if not provider:
            return Response(status=status.HTTP_403_FORBIDDEN)
        try:
            callback = provider.get_class().parse_callback(request.body, request.headers)
        except CallbackAuthenticationError, CallbackUnsupportedError, ImportError:
            return Response(status=status.HTTP_403_FORBIDDEN)
        except CallbackPayloadError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        payment_id = callback["payment_id"]
        payment_status = callback["status"]
        if payment_status not in (PaymentStatus.PENDING, PaymentStatus.SUCCESS, PaymentStatus.FAILED):
            return Response(status=status.HTTP_400_BAD_REQUEST)
        if payment_status == PaymentStatus.PENDING:
            return Response(status=status.HTTP_200_OK)

        attempt = (
            models.Attempt.objects.filter(
                payment_id=payment_id,
                provider=provider,
                status__in=[models.Attempt.STATUS.PENDING, models.Attempt.STATUS.TIMED_OUT],
            )
            .order_by("-created")
            .first()
        )
        # Повторный или поздний callback уже закрытой попытки безопасно подтверждаем без изменений.
        if not attempt:
            return Response(status=status.HTTP_200_OK)

        result = finalize_attempt(payment_id, attempt.pk, payment_status)
        if result is False:
            # Попытка неуспешна - продолжаем каскад на следующего провайдера.
            schedule_payment(payment_id)

        return Response(status=status.HTTP_200_OK)
