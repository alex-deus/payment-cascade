import asyncio
from decimal import Decimal
from threading import Event, Thread
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from django.db import close_old_connections
from django.test import TransactionTestCase

from apps.payment.models import Payment, Provider
from apps.payment.tasks import make_payment
from apps.users.models import User


class ConcurrentMakePaymentTests(TransactionTestCase):
    def test_two_payments_cannot_reserve_same_funds(self) -> None:
        user = User.objects.create_user(username="payer", balance="10.00")
        first = Payment.objects.create(user=user, amount="10.00", idempotency_key="first")
        second = Payment.objects.create(user=user, amount="10.00", idempotency_key="second")
        Provider.objects.create(name="First", slug="provider_a")
        started = Event()
        release = Event()
        errors = []

        async def create(_payment: Payment) -> dict:
            started.set()
            if not await asyncio.to_thread(release.wait, 5):
                raise TimeoutError("Test did not release provider")
            return {"status": "SUCCESS"}

        def first_task() -> None:
            try:
                make_payment.run(first.pk)
            except Exception as error:
                errors.append(error)
            finally:
                close_old_connections()

        provider = SimpleNamespace(create=AsyncMock(side_effect=create))
        with patch.object(Provider, "get_class", return_value=provider):
            thread = Thread(target=first_task)
            thread.start()
            try:
                self.assertTrue(started.wait(5))
                make_payment.run(second.pk)
            finally:
                release.set()
                thread.join(5)

        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(provider.create.call_count, 1)
        first.refresh_from_db()
        second.refresh_from_db()
        user.refresh_from_db()
        self.assertEqual(first.status, Payment.STATUS.SUCCEED)
        self.assertEqual(second.status, Payment.STATUS.FAILED)
        self.assertEqual(user.balance, Decimal("0.00"))
        self.assertEqual(user.frozen_balance, Decimal("0.00"))

    def test_second_task_does_not_call_provider_while_first_is_in_flight(self) -> None:
        user = User.objects.create_user(username="payer", balance="100.00")
        payment = Payment.objects.create(user=user, amount="10.00", idempotency_key="key")
        Provider.objects.create(name="First", slug="provider_a")
        started = Event()
        release = Event()
        errors = []

        async def create(_payment: Payment) -> dict:
            started.set()
            if not await asyncio.to_thread(release.wait, 5):
                raise TimeoutError("Test did not release provider")
            return {"id": "provider-payment", "status": "SUCCESS"}

        def first_task() -> None:
            try:
                make_payment.run(payment.pk)
            except Exception as error:
                errors.append(error)
            finally:
                close_old_connections()

        provider = SimpleNamespace(create=AsyncMock(side_effect=create))
        with patch.object(Provider, "get_class", return_value=provider):
            thread = Thread(target=first_task)
            thread.start()
            try:
                self.assertTrue(started.wait(5))
                make_payment.run(payment.pk)
            finally:
                release.set()
                thread.join(5)

        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(provider.create.call_count, 1)

        payment.refresh_from_db()

        self.assertEqual(payment.status, Payment.STATUS.SUCCEED)
        self.assertEqual(payment.attempts.count(), 1)
