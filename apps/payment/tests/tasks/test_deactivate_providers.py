from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from django_dynamic_fixture import G

from apps.payment.models import Attempt, Config, Payment, Provider
from apps.payment.tasks import deactivate_providers
from apps.users.models import User


class DeactivateProvidersTests(TestCase):
    payment: Payment
    provider: Provider

    def setUp(self) -> None:
        config: Config = Config.get_solo()
        config.max_count_of_failed_attempts = 2
        config.save()
        user: User = G(User)
        self.payment = G(Payment, user=user, amount="10.00", idempotency_key="deactivate-test")
        self.provider = G(Provider, name="First", slug="provider_a", is_active=True)

    def create_attempt(self, provider: Provider, status: str, created: datetime | None = None) -> Attempt:
        attempt: Attempt = G(Attempt, payment=self.payment, provider=provider, status=status)
        if created is not None:
            Attempt.objects.filter(pk=attempt.pk).update(created=created)
        return attempt

    def test_deactivates_only_providers_above_threshold(self) -> None:
        other: Provider = G(Provider, name="Second", slug="provider_b", is_active=True)
        for _ in range(3):
            self.create_attempt(self.provider, Attempt.STATUS.FAILED)
        for _ in range(2):
            self.create_attempt(other, Attempt.STATUS.FAILED)

        deactivate_providers.run()

        self.provider.refresh_from_db()
        other.refresh_from_db()
        self.assertFalse(self.provider.is_active)
        self.assertTrue(other.is_active)

        with self.assertNoLogs("celery.tasks", level="WARNING"):
            deactivate_providers.run()
        self.provider.refresh_from_db()
        other.refresh_from_db()
        self.assertFalse(self.provider.is_active)
        self.assertTrue(other.is_active)

    def test_counts_only_recent_failed_attempts(self) -> None:
        now = timezone.now()
        self.create_attempt(self.provider, Attempt.STATUS.FAILED, now - timedelta(minutes=30))
        self.create_attempt(self.provider, Attempt.STATUS.FAILED, now - timedelta(hours=1, microseconds=1))
        self.create_attempt(self.provider, Attempt.STATUS.SUCCEED, now - timedelta(minutes=10))
        self.create_attempt(self.provider, Attempt.STATUS.PENDING, now - timedelta(minutes=10))

        with patch("apps.payment.tasks.timezone.now", return_value=now):
            deactivate_providers.run()

        self.provider.refresh_from_db()
        self.assertTrue(self.provider.is_active)

    def test_attempt_at_one_hour_boundary_is_counted(self) -> None:
        now = timezone.now()
        self.create_attempt(self.provider, Attempt.STATUS.FAILED, now - timedelta(hours=1))
        self.create_attempt(self.provider, Attempt.STATUS.FAILED, now - timedelta(minutes=30))
        self.create_attempt(self.provider, Attempt.STATUS.FAILED, now - timedelta(minutes=10))

        with patch("apps.payment.tasks.timezone.now", return_value=now):
            deactivate_providers.run()

        self.provider.refresh_from_db()
        self.assertFalse(self.provider.is_active)

    def test_inactive_provider_stays_inactive_and_task_is_idempotent(self) -> None:
        self.provider.is_active = False
        self.provider.save(update_fields=["is_active"])
        for _ in range(3):
            self.create_attempt(self.provider, Attempt.STATUS.FAILED)

        with self.assertNoLogs("celery.tasks", level="WARNING"):
            deactivate_providers.run()
            deactivate_providers.run()

        self.provider.refresh_from_db()
        self.assertFalse(self.provider.is_active)

    def test_no_attempts_leave_provider_active(self) -> None:
        deactivate_providers.run()

        self.provider.refresh_from_db()
        self.assertTrue(self.provider.is_active)
