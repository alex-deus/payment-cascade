from django_filters import rest_framework as filters

from apps.payment import models


__all__ = ["ProviderFilter", "PaymentFilter"]


class ProviderFilter(filters.FilterSet):
    class Meta:
        model = models.Provider
        fields = {
            "is_active": ["exact"],
        }


class PaymentFilter(filters.FilterSet):
    class Meta:
        model = models.Payment
        fields = {
            "status": ["exact", "in"],
            "created": ["exact", "lt", "gt", "range"],
            "updated": ["exact", "lt", "gt", "range"],
        }
