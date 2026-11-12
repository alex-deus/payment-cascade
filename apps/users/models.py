from decimal import Decimal
from uuid import uuid4

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import F
from django.utils.translation import gettext_lazy as _


__all__ = ["User"]


class User(AbstractUser):
    class ROLE(models.TextChoices):
        USER = "user", _("User")
        ADMIN = "admin", _("Admin")

    class THEME(models.TextChoices):
        DARK = "dark", _("Dark")
        LIGHT = "light", _("Light")

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    email = models.EmailField(_("Email"), blank=True, null=True)
    role = models.CharField(_("Role"), max_length=16, choices=ROLE.choices, default=ROLE.USER)
    balance = models.DecimalField(_("Balance"), max_digits=18, decimal_places=2, default=Decimal("0.00"))
    frozen_balance = models.DecimalField(_("Frozen balance"), max_digits=18, decimal_places=2, default=Decimal("0.00"))

    name = models.CharField(_("Name"), max_length=64, blank=True, null=True)

    def __str__(self) -> str:
        return self.email or self.name or str(self.id)

    class Meta:
        app_label = "users"
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        constraints = [
            models.CheckConstraint(condition=models.Q(frozen_balance__gte=0), name="user_frozen_balance_nonnegative"),
            models.CheckConstraint(
                condition=models.Q(balance__gte=F("frozen_balance")), name="user_balance_covers_frozen"
            ),
        ]

    def withdraw(self, amount: Decimal) -> bool:
        if amount <= 0:
            raise ValueError("Amount must be positive")

        updated: int = User.objects.filter(id=self.pk, balance__gte=F("frozen_balance") + amount).update(
            balance=F("balance") - amount
        )

        return updated == 1
