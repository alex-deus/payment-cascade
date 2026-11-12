from importlib import import_module
from uuid import uuid4

from django.db import models
from django.template.defaultfilters import truncatechars
from django.utils.translation import gettext_lazy as _
from solo.models import SingletonModel

from .provider import ProviderBase


__all__ = ["Config", "Provider", "Payment", "Attempt"]


class Config(SingletonModel):
    max_count_of_failed_attempts = models.PositiveIntegerField(
        _("Max failed attempts per provider"),
        default=10,
        help_text=_("Deactivate the provider when its number of failed attempts per hour exceeds this value"),
    )
    payment_timeout_minutes = models.PositiveIntegerField(
        _("Payment timeout (minutes)"),
        default=30,
        help_text=_("Mark a pending payment as failed when it has not been completed within this number of minutes"),
    )
    attempt_timeout_minutes = models.PositiveIntegerField(
        _("Attempt timeout (minutes)"),
        default=30,
        help_text=_("Mark a pending attempt as failed when it has not been completed within this number of minutes"),
    )

    def __str__(self) -> str:
        return "Config"

    class Meta:
        app_label = "payment"
        verbose_name = _("config")
        verbose_name_plural = _("Config")


class Provider(models.Model):
    id = models.UUIDField(_("ID"), primary_key=True, default=uuid4, editable=False)
    name = models.CharField(_("Name"), max_length=128, unique=True)
    slug = models.SlugField(_("Slug"), max_length=128, unique=True)
    is_active = models.BooleanField(_("Is active"), default=True)
    data = models.JSONField(_("Data"), default=dict, blank=True, null=True)

    def __str__(self) -> str:
        return truncatechars(self.name, 32)

    class Meta:
        app_label = "payment"
        verbose_name = _("provider")
        verbose_name_plural = _("Providers")

    def get_class(self) -> ProviderBase:
        module_name = f"apps.payment.provider.{self.slug}"
        try:
            module = import_module(module_name)
        except ModuleNotFoundError as e:
            raise ImportError(f"Provider module not found: {module_name}") from e

        return module.Provider(self.data)


class Payment(models.Model):
    class STATUS(models.TextChoices):
        CREATED = "created", _("Created")
        PENDING = "pending", _("Pending")
        SUCCEED = "succeed", _("Succeed")
        FAILED = "failed", _("Failed")
        TIMED_OUT = "timed_out", _("Timed Out")

    id = models.UUIDField(_("ID"), primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey("users.User", models.CASCADE, verbose_name=_("User"), related_name="stories")
    status = models.CharField(_("Status"), max_length=32, choices=STATUS.choices, default=STATUS.CREATED)
    idempotency_key = models.CharField(_("Idempotency key"), max_length=128)

    amount = models.DecimalField(_("Amount"), max_digits=18, decimal_places=2)
    funds_reserved = models.BooleanField(_("Funds reserved"), default=False, editable=False)

    created = models.DateTimeField(_("Created"), auto_now_add=True)
    updated = models.DateTimeField(_("Updated"), auto_now=True)

    def __str__(self) -> str:
        return str(self.id)

    class Meta:
        app_label = "payment"
        ordering = ["-created"]
        verbose_name = _("payment")
        verbose_name_plural = _("Payments")
        constraints = [
            models.UniqueConstraint(fields=["user", "idempotency_key"], name="payment_unique_user_idempotency_key"),
        ]


class Attempt(models.Model):
    class STATUS(models.TextChoices):
        PENDING = "pending", _("Pending")
        SUCCEED = "succeed", _("Succeed")
        FAILED = "failed", _("Failed")
        TIMED_OUT = "timed_out", _("Timed Out")

    id = models.UUIDField(_("ID"), primary_key=True, default=uuid4, editable=False)
    payment = models.ForeignKey("Payment", models.CASCADE, related_name="attempts")
    provider = models.ForeignKey("Provider", models.PROTECT, related_name="providers")
    status = models.CharField(_("Status"), max_length=32, choices=STATUS.choices, default=STATUS.PENDING)

    created = models.DateTimeField(_("Created"), auto_now_add=True)
    updated = models.DateTimeField(_("Updated"), auto_now=True)

    def __str__(self) -> str:
        return str(self.id)

    class Meta:
        app_label = "payment"
        ordering = ["-created"]
        verbose_name = _("attempt")
        verbose_name_plural = _("Attempts")
