from decimal import Decimal

from django.test import TransactionTestCase
from django.urls import reverse

from apps.users.models import User


class UserAdminBalanceTests(TransactionTestCase):
    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(username="admin", password="password")
        self.user = User.objects.create_user(username="payer", password="password", balance=Decimal("100.00"))
        self.client.force_login(self.admin)

    def test_stale_form_does_not_overwrite_balance_after_withdrawal(self) -> None:
        url = reverse("admin:users_user_change", args=[self.user.pk])
        response = self.client.get(url)
        form = response.context["adminform"].form
        version = form.initial["balance_version"]
        self.assertTrue(self.user.withdraw(Decimal("10.00")))

        response = self.client.post(
            url,
            {
                "username": self.user.username,
                "role": self.user.role,
                "name": "New name",
                "email": "",
                "balance": "100.00",
                "balance_version": version,
                "date_joined_0": self.user.date_joined.strftime("%Y-%m-%d"),
                "date_joined_1": self.user.date_joined.strftime("%H:%M:%S"),
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("balance_version", response.context["adminform"].form.errors)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal("90.00"))

    def test_password_change_post_succeeds(self) -> None:
        url = reverse("admin:auth_user_password_change", args=[self.user.pk])

        response = self.client.post(url, {"password1": "changed-password-123", "password2": "changed-password-123"})

        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("changed-password-123"))
