from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path
from django.utils.translation import gettext_lazy as _


admin.site.site_header = _("Grandpa O - Admin")
admin.site.site_title = _("Admin")
admin.site.index_title = _("Welcome to Grandpa O")

urlpatterns = [
    path("api/v1/", include(("apps.api.urls", "apps.api"), namespace="api_v1")),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(prefix=settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
