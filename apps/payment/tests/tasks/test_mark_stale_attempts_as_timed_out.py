from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from django_dynamic_fixture import G

from apps.payment.models import Attempt, Config, Payment, Provider
from apps.payment.tasks import mark_stale_attempts_as_timed_out
from apps.users.models import User


class MarkStaleAttemptsAsTimedOutTests(TestCase):
    payment: Payment
    provider: Provider
    now: datetime

    def setUp(self) -> None:
        config: Config = Config.get_solo()
        config.attempt_timeout_minutes = 15
        config.save()
        user: User = G(User)
        self.payment = G(Payment, user=user, amount="10.00", idempotency_key="timeout-test")
        self.provider = G(Provider, name="Provider", slug="provider_a")
        self.now = timezone.now()

    def create_attempt(self, status: str, created: datetime) -> Attempt:
        attempt: Attempt = G(Attempt, payment=self.payment, provider=self.provider, status=status)
        Attempt.objects.filter(pk=attempt.pk).update(created=created)
        return attempt

    def run_task(self) -> None:
        with patch("apps.payment.tasks.timezone.now", return_value=self.now):
            mark_stale_attempts_as_timed_out.run()

    def test_marks_only_pending_attempts_older_than_configured_timeout(self) -> None:
        stale: Attempt = self.create_attempt(Attempt.STATUS.PENDING, self.now - timedelta(minutes=15, microseconds=1))
        boundary: Attempt = self.create_attempt(Attempt.STATUS.PENDING, self.now - timedelta(minutes=15))
        recent: Attempt = self.create_attempt(Attempt.STATUS.PENDING, self.now - timedelta(minutes=14))

        self.run_task()

        stale.refresh_from_db()
        boundary.refresh_from_db()
        recent.refresh_from_db()
        self.assertEqual(stale.status, Attempt.STATUS.TIMED_OUT)
        self.assertEqual(boundary.status, Attempt.STATUS.PENDING)
        self.assertEqual(recent.status, Attempt.STATUS.PENDING)

    def test_preserves_completed_and_timed_out_attempts(self) -> None:
        attempts: list[Attempt] = [
            self.create_attempt(status, self.now - timedelta(hours=1))
            for status in (Attempt.STATUS.SUCCEED, Attempt.STATUS.FAILED, Attempt.STATUS.TIMED_OUT)
        ]

        self.run_task()

        for attempt, expected_status in zip(
            attempts, (Attempt.STATUS.SUCCEED, Attempt.STATUS.FAILED, Attempt.STATUS.TIMED_OUT), strict=True
        ):
            with self.subTest(status=expected_status):
                attempt.refresh_from_db()
                self.assertEqual(attempt.status, expected_status)

    def test_repeated_run_preserves_timed_out_status_and_payment(self) -> None:
        attempt: Attempt = self.create_attempt(Attempt.STATUS.PENDING, self.now - timedelta(hours=1))
        original_payment_status = self.payment.status

        self.run_task()
        self.run_task()

        attempt.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual(attempt.status, Attempt.STATUS.TIMED_OUT)
        self.assertEqual(self.payment.status, original_payment_status)

    def test_no_attempts(self) -> None:
        self.run_task()
        self.assertFalse(Attempt.objects.exists())
