from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm
from django.core import signing
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rangefilter.filters import DateTimeRangeFilterBuilder

from apps.common.admin import JSONFieldAdminMixin
from . import models


class UserChangeForm(BaseUserChangeForm):
    balance_version = forms.CharField(widget=forms.HiddenInput)

    class Meta(BaseUserChangeForm.Meta):
        model = models.User
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and not self.instance._state.adding:
            self.initial["balance_version"] = signing.dumps([str(self.instance.pk), str(self.instance.balance)])

    def clean_balance_version(self):
        value = self.cleaned_data["balance_version"]
        try:
            version = signing.loads(value)
        except signing.BadSignature:
            raise forms.ValidationError(_("Invalid balance version. Reload the page.")) from None
        if version != [str(self.instance.pk), str(self.instance.balance)]:
            raise forms.ValidationError(_("Balance changed since this page was opened. Reload and try again."))
        return value

    def clean_balance(self):
        balance = self.cleaned_data["balance"]
        if balance < self.instance.frozen_balance:
            raise forms.ValidationError(_("Balance cannot be less than frozen funds."))
        return balance


@admin.register(models.User)
class UserAdmin(JSONFieldAdminMixin, UserAdmin):
    form = UserChangeForm
    readonly_fields = ["frozen_balance"]
    radio_fields = {"role": admin.HORIZONTAL}
    add_fieldsets = (
        (
            _("Credentials"),
            {"classes": ("wide",), "fields": ("role", "username", "email", "password1", "password2")},
        ),
        (
            _("Django-admin group"),
            {"classes": ("wide",), "fields": ("is_superuser", "is_active", "is_staff", "groups")},
        ),
    )
    list_display = ["id", "email", "role", "balance", "is_superuser", "date_joined", "name"]
    list_filter = ["role", "is_superuser", ("date_joined", DateTimeRangeFilterBuilder())]
    search_fields = ["id", "email", "username", "name"]
    ordering = ["-date_joined"]
    filter_horizontal = ["groups", "user_permissions"]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "role",
                    "username",
                    "name",
                    "email",
                    "password",
                    "balance",
                    "balance_version",
                    "frozen_balance",
                )
            },
        ),
        (_("Important dates"), {"classes": ["collapse"], "fields": ("last_login", "date_joined")}),
        (
            _("Permissions"),
            {
                "classes": ["collapse"],
                "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
            },
        ),
    )

    def get_object(self, request, object_id, from_field=None):
        if request.method == "POST":
            return self.get_queryset(request).select_for_update().filter(pk=object_id).first()
        return super().get_object(request, object_id, from_field)

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def user_change_password(self, request, id, form_url=""):
        with transaction.atomic():
            return super().user_change_password(request, id, form_url)
