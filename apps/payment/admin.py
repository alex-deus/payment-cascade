from django.contrib import admin
from django.db.models import JSONField, TextField
from django.forms import Textarea
from django.template.defaultfilters import truncatechars
from django.urls import reverse
from django.utils.safestring import SafeString
from django.utils.translation import gettext_lazy as _
from jsoneditor.forms import JSONEditor
from rangefilter.filters import DateTimeRangeFilterBuilder, NumericRangeFilterBuilder
from solo.admin import SingletonModelAdmin

from apps.common.admin import JSONFieldAdminMixin
from . import models


@admin.register(models.Config)
class ConfigAdmin(JSONFieldAdminMixin, SingletonModelAdmin): ...


@admin.register(models.Provider)
class ProviderAdmin(JSONFieldAdminMixin, admin.ModelAdmin):
    formfield_overrides = {
        JSONField: {
            "widget": JSONEditor(
                attrs={"style": "min-height: 500px; height: 500px"},
                init_options={"mode": "code", "modes": ["code", "tree"]},
            )
        },
        TextField: {"widget": Textarea(attrs={"rows": 20, "style": "width: 100%"})},
    }
    search_fields = ["id", "name"]
    list_display = ["get_id", "get_name", "is_active"]

    @admin.display(description=_("ID"))
    def get_id(self, obj: models.Provider) -> str:
        return f"{obj.pk.hex[:4]}...{obj.pk.hex[28:]}"

    @admin.display(description=_("Name"))
    def get_name(self, obj: models.Provider) -> str:
        return truncatechars(obj.name, 32)


@admin.register(models.Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["get_id", "user", "amount", "status", "created", "updated"]
    list_filter = [
        "status",
        ("amount", NumericRangeFilterBuilder()),
        ("created", DateTimeRangeFilterBuilder()),
        ("updated", DateTimeRangeFilterBuilder()),
    ]
    search_fields = ["id", "user__email"]
    autocomplete_fields = ["user"]

    radio_fields = {"status": admin.HORIZONTAL}
    readonly_fields = ["status", "funds_reserved", "created", "updated"]
    fieldsets = (
        (_("Main"), {"fields": ("user", "status", "amount", "funds_reserved")}),
        (_("Dates"), {"classes": ["collapse"], "fields": ("created", "updated")}),
    )

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)

        return [*fields, "user", "amount"] if obj else fields

    def get_object(self, request, object_id, from_field=None):
        if request.method == "POST":
            return self.get_queryset(request).select_for_update().filter(pk=object_id).first()
        return super().get_object(request, object_id, from_field)

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    @admin.display(description=_("ID"))
    def get_id(self, obj: models.Payment) -> str:
        return f"{obj.pk.hex[:4]}...{obj.pk.hex[28:]}"

    @admin.display(description=_("User"))
    def get_user(self, obj: models.Payment) -> SafeString:
        url = reverse("admin:users_user_change", args=[obj.user.pk])
        text = obj.user.email or obj.user.name or f"{obj.user.pk.hex[:4]}...{obj.user.pk.hex[28:]}"

        return SafeString(f'<a href="{url}">{text}</a>')


@admin.register(models.Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ["get_id", "payment", "provider", "status", "created", "updated"]
    list_filter = ["created", "updated", "provider"]
    search_fields = ["id", "provider__name"]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    @admin.display(description=_("ID"))
    def get_id(self, obj: models.Provider) -> str:
        return f"{obj.pk.hex[:4]}...{obj.pk.hex[28:]}"
