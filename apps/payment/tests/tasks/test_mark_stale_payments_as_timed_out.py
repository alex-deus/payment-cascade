from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from django_dynamic_fixture import G

from apps.payment.models import Attempt, Payment, Provider
from apps.payment.tasks import mark_stale_payments_as_timed_out
from apps.users.models import User


class MarkStalePaymentsAsTimedOutTests(TestCase):
    def setUp(self) -> None:
        self.user = G(User)
        self.now = timezone.now()

    def create_payment(self, status: str, age: timedelta) -> Payment:
        payment = G(Payment, user=self.user, status=status, idempotency_key=str(Payment.objects.count()))
        Payment.objects.filter(pk=payment.pk).update(created=self.now - age)
        return payment

    def run_task(self) -> None:
        with (
            patch("apps.payment.tasks.timezone.now", return_value=self.now),
            patch("apps.payment.tasks.Config.get_solo") as get_config,
        ):
            get_config.return_value.payment_timeout_minutes = 15
            mark_stale_payments_as_timed_out.run()

    def test_times_out_both_eligible_statuses(self) -> None:
        statuses = (Payment.STATUS.CREATED, Payment.STATUS.PENDING)
        payments = [self.create_payment(status, timedelta(minutes=16)) for status in statuses]

        self.run_task()

        for payment in payments:
            with self.subTest(status=payment.status):
                payment.refresh_from_db()
                self.assertEqual(payment.status, Payment.STATUS.TIMED_OUT)

    def test_preserves_payments_at_boundary_and_more_recent(self) -> None:
        payments = [self.create_payment(Payment.STATUS.PENDING, timedelta(minutes=minutes)) for minutes in (15, 14)]

        self.run_task()

        for payment in payments:
            payment.refresh_from_db()
            self.assertEqual(payment.status, Payment.STATUS.PENDING)

    def test_preserves_terminal_statuses_on_repeated_runs(self) -> None:
        statuses = (Payment.STATUS.SUCCEED, Payment.STATUS.FAILED, Payment.STATUS.TIMED_OUT)
        payments = [self.create_payment(status, timedelta(hours=1)) for status in statuses]

        self.run_task()
        self.run_task()

        for payment, status in zip(payments, statuses, strict=True):
            with self.subTest(status=status):
                payment.refresh_from_db()
                self.assertEqual(payment.status, status)

    def test_releases_reservation_when_every_attempt_failed(self) -> None:
        self.user.balance = 100
        self.user.frozen_balance = 10
        self.user.save(update_fields=["balance", "frozen_balance"])
        payment = self.create_payment(Payment.STATUS.PENDING, timedelta(minutes=16))
        Payment.objects.filter(pk=payment.pk).update(amount=10, funds_reserved=True)
        provider = G(Provider, name="Provider", slug="provider_a")
        G(Attempt, payment=payment, provider=provider, status=Attempt.STATUS.FAILED)

        self.run_task()

        payment.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(payment.status, Payment.STATUS.TIMED_OUT)
        self.assertFalse(payment.funds_reserved)
        self.assertEqual(self.user.frozen_balance, 0)

    def test_keeps_reservation_with_uncertain_attempt(self) -> None:
        self.user.balance = 100
        self.user.frozen_balance = 10
        self.user.save(update_fields=["balance", "frozen_balance"])
        payment = self.create_payment(Payment.STATUS.PENDING, timedelta(minutes=16))
        Payment.objects.filter(pk=payment.pk).update(amount=10, funds_reserved=True)
        provider = G(Provider, name="Provider", slug="provider_a")
        G(Attempt, payment=payment, provider=provider, status=Attempt.STATUS.TIMED_OUT)

        self.run_task()

        payment.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(payment.status, Payment.STATUS.TIMED_OUT)
        self.assertTrue(payment.funds_reserved)
        self.assertEqual(self.user.frozen_balance, 10)
