from drf_dynamic_fields import DynamicFieldsMixin
from rest_framework import serializers

from apps.payment.models import Payment, Provider


__all__ = [
    "PaymentCreateSerializer",
    "PaymentListSerializer",
    "PaymentRetrieveSerializer",
    "ProviderListSerializer",
    "ProviderRetrieveSerializer",
]


class PaymentCreateSerializer(serializers.ModelSerializer):
    idempotency_key = serializers.CharField(required=True, min_length=1, max_length=255)

    class Meta:
        model = Payment
        fields = ["idempotency_key"]

    def validate(self, data: dict) -> dict:
        ...

        return data


class PaymentListSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ["id", "status", "status_display", "created", "updated"]

    @staticmethod
    def get_status_display(obj: Payment) -> str:
        return obj.get_status_display()


class PaymentRetrieveSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ["id", "status", "status_display", "created", "updated"]

    @staticmethod
    def get_status_display(obj: Payment) -> str:
        return obj.get_status_display()


class ProviderListSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Provider
        fields = ["id", "name", "is_active"]


class ProviderRetrieveSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Provider
        fields = ["id", "name", "is_active"]
