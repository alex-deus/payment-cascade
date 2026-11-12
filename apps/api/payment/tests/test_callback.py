import json
from decimal import Decimal
from threading import Barrier, Thread
from unittest.mock import patch
from uuid import uuid4

from django.db import connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from rest_framework.test import APIClient

from apps.payment.models import Attempt, Payment, Provider
from apps.payment.provider.base import PaymentStatus
from apps.payment.provider.provider_b import sign
from apps.payment.tasks import make_payment, resume_failed_payments
from apps.users.models import User


class ProviderCallbackTests(TransactionTestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="payer", balance="100.00", frozen_balance="10.00")
        self.payment = Payment.objects.create(
            user=self.user, amount="10.00", status=Payment.STATUS.PENDING, funds_reserved=True, idempotency_key="key"
        )
        self.provider = Provider.objects.create(name="B", slug="provider_b", data={"callback_secret": "secret"})
        self.attempt = Attempt.objects.create(payment=self.payment, provider=self.provider)
        self.client = APIClient()
        self.url = "/api/v1/payments/callback/provider_b/"

    def send(self, payload: object, secret: str = "secret", url: str | None = None) -> object:
        body = json.dumps(payload).encode()
        return self.client.post(
            url or self.url, data=body, content_type="application/json", HTTP_X_SIGNATURE=sign(secret, body)
        )

    def test_success_and_replay_debit_once(self) -> None:
        payload = {"order_id": str(self.payment.pk), "status": "success"}

        first = self.send(payload)
        second = self.send(payload)

        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.payment.refresh_from_db()
        self.attempt.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS.SUCCEED)
        self.assertEqual(self.attempt.status, Attempt.STATUS.SUCCEED)
        self.assertEqual(self.user.balance, Decimal("90.00"))
        self.assertEqual(self.user.frozen_balance, Decimal("0.00"))
        self.assertFalse(self.payment.funds_reserved)

    def test_inactive_provider_can_complete_pending_attempt(self) -> None:
        self.provider.is_active = False
        self.provider.save(update_fields=["is_active"])

        response = self.send({"order_id": str(self.payment.pk), "status": "success"})

        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS.SUCCEED)

    def test_failed_callback_schedules_cascade_once(self) -> None:
        payload = {"order_id": str(self.payment.pk), "status": "failed"}

        with patch("apps.payment.tasks.make_payment.apply_async") as publish:
            first = self.send(payload)
            second = self.send(payload)

        self.assertEqual((first.status_code, second.status_code), (200, 200))
        publish.assert_called_once()
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, Attempt.STATUS.FAILED)
        self.payment.refresh_from_db()
        self.assertTrue(self.payment.funds_reserved)

    def test_failed_callback_recovers_after_broker_failure(self) -> None:
        payload = {"order_id": str(self.payment.pk), "status": "failed"}

        with patch("apps.payment.tasks.make_payment.apply_async", side_effect=OSError("broker unavailable")):
            response = self.send(payload)
        with patch("apps.payment.tasks.make_payment.apply_async") as publish:
            resume_failed_payments.run()

        self.assertEqual(response.status_code, 200)
        publish.assert_called_once_with(args=[str(self.payment.pk)], task_id=f"make_payment:{self.payment.pk}")

    def test_recovery_ignores_unresolved_attempts(self) -> None:
        other = Provider.objects.create(name="A", slug="provider_a")
        Attempt.objects.create(payment=self.payment, provider=other, status=Attempt.STATUS.FAILED)

        with patch("apps.payment.tasks.make_payment.apply_async") as publish:
            resume_failed_payments.run()

        publish.assert_not_called()

    def test_authentication_failures_do_not_change_payment(self) -> None:
        body = json.dumps({"order_id": str(self.payment.pk), "status": "success"}).encode()
        self.provider.data = {}
        self.provider.save(update_fields=["data"])

        no_secret = self.client.post(
            self.url, data=body, content_type="application/json", HTTP_X_SIGNATURE=sign("", body)
        )
        self.provider.data = {"callback_secret": "secret"}
        self.provider.save(update_fields=["data"])
        no_signature = self.client.post(self.url, data=body, content_type="application/json")
        malformed = self.client.post(self.url, data=body, content_type="application/json", HTTP_X_SIGNATURE="é")
        wrong = self.send({"order_id": str(self.payment.pk), "status": "success"}, secret="wrong")
        unknown = self.send(
            {"order_id": str(self.payment.pk), "status": "success"}, url="/api/v1/payments/callback/nope/"
        )

        self.assertEqual([r.status_code for r in (no_secret, no_signature, malformed, wrong, unknown)], [403] * 5)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS.PENDING)

    def test_bad_payloads_rejected(self) -> None:
        for payload in (
            [],
            None,
            {},
            {"order_id": "bad", "status": "success"},
            {"order_id": str(self.payment.pk), "status": "unexpected"},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(self.send(payload).status_code, 400)

    def test_signed_invalid_utf8_rejected(self) -> None:
        body = b"\xff"

        response = self.client.post(
            self.url, data=body, content_type="application/json", HTTP_X_SIGNATURE=sign("secret", body)
        )

        self.assertEqual(response.status_code, 400)

    def test_pending_and_unknown_payment_do_not_change_state(self) -> None:
        pending = self.send({"order_id": str(self.payment.pk), "status": "pending"})
        unknown = self.send({"order_id": str(uuid4()), "status": "success"})

        self.assertEqual((pending.status_code, unknown.status_code), (200, 200))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS.PENDING)

    def test_attempt_must_belong_to_provider(self) -> None:
        self.attempt.delete()
        other = Provider.objects.create(name="A", slug="provider_a")
        Attempt.objects.create(payment=self.payment, provider=other)

        response = self.send({"order_id": str(self.payment.pk), "status": "success"})

        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS.PENDING)

    def test_callback_for_provider_without_protocol_is_rejected(self) -> None:
        Provider.objects.create(name="A", slug="provider_a", data={"callback_secret": "secret"})

        response = self.send(
            {"order_id": str(self.payment.pk), "status": "success"}, url="/api/v1/payments/callback/provider_a/"
        )

        self.assertEqual(response.status_code, 403)

    def test_unsupported_adapter_status_does_not_finalize_attempt(self) -> None:
        payload = {"order_id": str(self.payment.pk), "status": "success"}

        with patch(
            "apps.payment.provider.provider_b.Provider.parse_callback",
            return_value={"payment_id": self.payment.pk, "status": PaymentStatus.REFUNDED},
        ):
            response = self.send(payload)

        self.assertEqual(response.status_code, 400)
        self.payment.refresh_from_db()
        self.attempt.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS.PENDING)
        self.assertEqual(self.attempt.status, Attempt.STATUS.PENDING)

    def test_timed_out_attempt_and_payment_can_succeed(self) -> None:
        self.payment.status = Payment.STATUS.TIMED_OUT
        self.payment.save(update_fields=["status", "updated"])
        self.attempt.status = Attempt.STATUS.TIMED_OUT
        self.attempt.save(update_fields=["status", "updated"])

        response = self.send({"order_id": str(self.payment.pk), "status": "success"})

        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS.SUCCEED)

    def test_success_callback_before_create_returns(self) -> None:
        self.attempt.delete()
        self.payment.status = Payment.STATUS.CREATED
        self.payment.funds_reserved = False
        self.payment.save(update_fields=["status", "funds_reserved", "updated"])
        self.user.frozen_balance = 0
        self.user.save(update_fields=["frozen_balance"])

        def create(payment: Payment) -> dict:
            response = self.send({"order_id": str(payment.pk), "status": "success"})
            self.assertEqual(response.status_code, 200)
            return {"id": "provider-id", "status": PaymentStatus.PENDING}

        with patch("apps.payment.provider.provider_b.Provider.create", side_effect=create):
            make_payment.run(self.payment.pk)

        self.payment.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS.SUCCEED)
        self.assertEqual(self.user.balance, Decimal("90.00"))
        self.assertEqual(self.user.frozen_balance, Decimal("0.00"))

    @skipUnlessDBFeature("has_select_for_update")
    def test_simultaneous_success_callbacks_debit_once(self) -> None:
        body = json.dumps({"order_id": str(self.payment.pk), "status": "success"}).encode()
        barrier = Barrier(2)
        results = []
        errors = []

        def send_callback() -> None:
            try:
                barrier.wait(timeout=5)
                response = APIClient().post(
                    self.url, data=body, content_type="application/json", HTTP_X_SIGNATURE=sign("secret", body)
                )
                results.append(response.status_code)
            except Exception as exc:
                errors.append(exc)
            finally:
                connections.close_all()

        threads = [Thread(target=send_callback), Thread(target=send_callback)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(sorted(results), [200, 200])
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal("90.00"))
        self.assertEqual(self.user.frozen_balance, Decimal("0.00"))
