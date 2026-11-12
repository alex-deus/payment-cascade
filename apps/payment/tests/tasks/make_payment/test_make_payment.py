from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from celery.exceptions import Retry
from django.db import DatabaseError, transaction
from django.test import TransactionTestCase
from django_dynamic_fixture import G

from apps.payment.models import Attempt, Payment, Provider
from apps.payment.provider.base import PaymentStatus
from apps.payment.tasks import make_payment
from apps.users.models import User


class MakePaymentTests(TransactionTestCase):
    user: User
    payment: Payment
    first: Provider
    second: Provider
    inactive: Provider

    def setUp(self) -> None:
        self.user: User = G(User, username="payer", balance=Decimal("100.00"))
        self.payment: Payment = G(Payment, user=self.user, amount="10.00", idempotency_key="key")
        self.first: Provider = G(Provider, name="First", slug="provider_a")
        self.second: Provider = G(Provider, name="Second", slug="provider_b")
        self.inactive: Provider = G(Provider, name="Inactive", slug="provider_c", is_active=False)

    def run_payment(self, *responses: object) -> AsyncMock:
        create = AsyncMock(side_effect=responses)
        with patch.object(Provider, "get_class", return_value=SimpleNamespace(create=create)):
            make_payment.run(self.payment.pk)

        self.payment.refresh_from_db()

        return create

    def test_failed_then_success(self) -> None:
        create = self.run_payment(
            {"id": None, "status": PaymentStatus.FAILED}, {"id": "provider-payment", "status": PaymentStatus.SUCCESS}
        )

        self.assertEqual(self.payment.status, Payment.STATUS.SUCCEED)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal("90.00"))
        self.assertEqual(self.user.frozen_balance, Decimal("0.00"))
        self.assertFalse(self.payment.funds_reserved)
        self.assertEqual(create.call_count, 2)
        self.assertEqual(
            list(self.payment.attempts.order_by("created").values_list("provider_id", "status")),
            [(self.first.pk, Attempt.STATUS.FAILED), (self.second.pk, Attempt.STATUS.SUCCEED)],
        )
        make_payment.run(self.payment.pk)
        self.assertEqual(self.payment.attempts.count(), 2)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal("90.00"))
        self.assertEqual(self.user.frozen_balance, Decimal("0.00"))

    def test_all_providers_failed(self) -> None:
        self.run_payment({"id": None, "status": "FAILED"}, {"id": None, "status": "FAILED"})
        self.assertEqual(self.payment.status, Payment.STATUS.FAILED)
        self.assertEqual(self.payment.attempts.count(), 2)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal("100.00"))
        self.assertEqual(self.user.frozen_balance, Decimal("0.00"))

    def test_pending_stops_cascade_and_repeated_task(self) -> None:
        create = self.run_payment({"id": "provider-payment", "status": "PENDING"})

        self.assertEqual(self.payment.status, Payment.STATUS.PENDING)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal("100.00"))
        self.assertEqual(self.user.frozen_balance, Decimal("10.00"))
        self.assertEqual(create.call_count, 1)
        self.run_payment({"id": "provider-payment", "status": "SUCCESS"}).assert_not_called()
        self.assertEqual(self.payment.attempts.count(), 1)

    def test_unknown_outcome_stops_cascade(self) -> None:
        for response in (RuntimeError("timeout"), {}, {"status": "unexpected"}, None):
            with self.subTest(response=response):
                self.payment.attempts.all().delete()
                self.payment.status = Payment.STATUS.CREATED
                self.payment.funds_reserved = False
                self.payment.save(update_fields=["status", "funds_reserved", "updated"])
                User.objects.filter(pk=self.user.pk).update(frozen_balance=Decimal("0.00"))

                with self.assertLogs("celery.tasks", level="ERROR"):
                    create = self.run_payment(response)

                self.assertEqual(create.call_count, 1)
                self.assertEqual(self.payment.status, Payment.STATUS.PENDING)
                self.assertEqual(self.payment.attempts.get().status, Attempt.STATUS.PENDING)
                self.user.refresh_from_db()
                self.assertEqual(self.user.frozen_balance, Decimal("10.00"))
                self.run_payment({"id": "provider-payment", "status": "SUCCESS"}).assert_not_called()

    def test_no_active_providers(self) -> None:
        Provider.objects.update(is_active=False)

        create = self.run_payment()
        create.assert_not_called()

        self.assertEqual(self.payment.status, Payment.STATUS.FAILED)
        self.assertFalse(self.payment.attempts.exists())

    def test_insufficient_available_balance_does_not_call_provider(self) -> None:
        User.objects.filter(pk=self.user.pk).update(balance=Decimal("9.00"))

        self.run_payment().assert_not_called()

        self.user.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS.FAILED)
        self.assertEqual(self.user.balance, Decimal("9.00"))
        self.assertEqual(self.user.frozen_balance, Decimal("0.00"))
        self.assertFalse(self.payment.attempts.exists())

    def test_timed_out_attempt_keeps_reservation_and_prevents_retry(self) -> None:
        self.run_payment({"status": PaymentStatus.PENDING})
        self.payment.attempts.update(status=Attempt.STATUS.TIMED_OUT)

        self.run_payment().assert_not_called()

        self.user.refresh_from_db()
        self.assertEqual(self.user.frozen_balance, Decimal("10.00"))
        self.assertTrue(self.payment.funds_reserved)

    def test_withdraw_cannot_spend_reserved_funds(self) -> None:
        self.run_payment({"status": PaymentStatus.PENDING})

        self.assertFalse(self.user.withdraw(Decimal("91.00")))
        self.assertTrue(self.user.withdraw(Decimal("90.00")))
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal("10.00"))
        self.assertEqual(self.user.frozen_balance, Decimal("10.00"))

    def test_resume_after_definitively_failed_attempt(self) -> None:
        G(Attempt, payment=self.payment, provider=self.first, status=Attempt.STATUS.FAILED)

        self.payment.status = Payment.STATUS.PENDING
        self.payment.save(update_fields=["status", "updated"])
        self.run_payment({"id": "provider-payment", "status": "SUCCESS"})

        self.assertEqual(self.payment.status, Payment.STATUS.SUCCEED)
        self.assertEqual(self.payment.attempts.filter(provider=self.second).get().status, Attempt.STATUS.SUCCEED)

    def test_provider_receives_config(self) -> None:
        self.first.data = {"key": "value"}
        self.assertEqual(self.first.get_class().data, {"key": "value"})

    def test_rejects_call_inside_atomic_before_contacting_provider(self) -> None:
        create = AsyncMock(return_value={"id": "provider-payment", "status": "SUCCESS"})
        with patch.object(Provider, "get_class", return_value=SimpleNamespace(create=create)):
            with transaction.atomic(), self.assertRaisesMessage(RuntimeError, "outside an existing transaction"):
                make_payment.run(self.payment.pk)

        create.assert_not_called()

        self.payment.refresh_from_db()

        self.assertEqual(self.payment.status, Payment.STATUS.CREATED)
        self.assertFalse(self.payment.attempts.exists())

    def test_database_error_schedules_retry_before_provider_call(self) -> None:
        with (
            patch("apps.payment.tasks.transaction.atomic", side_effect=DatabaseError("database unavailable")),
            patch.object(make_payment, "retry", side_effect=Retry()) as retry,
            patch.object(Provider, "get_class") as get_class,
            self.assertRaises(Retry),
        ):
            make_payment.run(self.payment.pk)

        retry.assert_called_once()

        get_class.assert_not_called()
        self.assertFalse(self.payment.attempts.exists())

    def test_database_error_after_provider_call_does_not_repeat_charge(self) -> None:
        create = AsyncMock(return_value={"id": "provider-payment", "status": "SUCCESS"})
        first_transaction = transaction.atomic()
        with (
            patch.object(Provider, "get_class", return_value=SimpleNamespace(create=create)),
            patch("apps.payment.tasks.transaction.atomic", side_effect=[first_transaction, DatabaseError("lost")]),
            patch.object(make_payment, "retry", side_effect=Retry()),
            self.assertRaises(Retry),
        ):
            make_payment.run(self.payment.pk)

        self.assertEqual(create.call_count, 1)
        self.run_payment({"id": "provider-payment", "status": "SUCCESS"}).assert_not_called()
        self.assertEqual(self.payment.status, Payment.STATUS.PENDING)
        self.assertEqual(self.payment.attempts.get().status, Attempt.STATUS.PENDING)
