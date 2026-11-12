from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views


router_report = DefaultRouter()
router_report.register("", views.PaymentViewSet, basename="payment")
router_report.register("providers", views.ProvidersViewSet, basename="provider")

# Путь callback объявлен до роутера, чтобы не конфликтовать с detail-маршрутом платежа.
urlpatterns = [
    path("callback/<slug:slug>/", views.ProviderCallbackView.as_view(), name="provider-callback"),
] + router_report.urls
