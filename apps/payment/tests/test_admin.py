from types import SimpleNamespace

from django.contrib import admin
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django_dynamic_fixture import G

from apps.payment.admin import AttemptAdmin
from apps.payment.models import Attempt, Config, Payment, Provider
from apps.users.models import User


class PaymentAdminSmokeTests(TestCase):
    admin_user: User
    provider: Provider
    payment: Payment
    config: Config

    @classmethod
    def setUpTestData(cls) -> None:
        cls.admin_user = G(User, is_staff=True, is_superuser=True, is_active=True)
        cls.provider = G(Provider, name="Provider A", slug="provider_a")
        cls.payment = G(Payment, user=cls.admin_user, amount="10.00", idempotency_key="admin-smoke")
        cls.config = Config.get_solo()

    def setUp(self) -> None:
        self.client.force_login(self.admin_user)

    def test_config_admin(self) -> None:
        response = self.client.get(reverse("admin:payment_config_changelist"), follow=True)
        self.assertEqual(response.status_code, 200)

    def test_provider_admin(self) -> None:
        for name, args in (
            ("admin:payment_provider_changelist", ()),
            ("admin:payment_provider_add", ()),
            ("admin:payment_provider_change", (self.provider.pk,)),
        ):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200)

    def test_payment_admin(self) -> None:
        for name, args in (
            ("admin:payment_payment_changelist", ()),
            ("admin:payment_payment_add", ()),
            ("admin:payment_payment_change", (self.payment.pk,)),
        ):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200)


class AttemptAdminTests(SimpleTestCase):
    def test_attempts_are_read_only(self) -> None:
        model_admin = AttemptAdmin(Attempt, admin.AdminSite())
        request = SimpleNamespace(user=SimpleNamespace(has_perm=lambda permission: True))

        self.assertTrue(model_admin.has_view_permission(request))
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
