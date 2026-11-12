from django.urls import include, path

from . import views


urlpatterns = [
    path("docs/", include(("apps.api.docs.urls", "apps.api"), namespace="docs")),
    path("payments/", include(("apps.api.payment.urls", "apps.api"), namespace="payment")),
    path("user/", include(("apps.api.user.urls", "apps.api"), namespace="user")),
    path("health/", views.HealthView.as_view(), name="health"),
]
