from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
from urllib import error, parse, request
from uuid import UUID

from django.conf import settings

from .base import (
    CallbackAuthenticationError,
    CallbackPayloadError,
    CallbackResult,
    CancellationResult,
    CancellationStatus,
    CreatePaymentResult,
    PaymentStatus,
    ProviderBase,
    RefundResult,
    RefundStatus,
)


if TYPE_CHECKING:
    from apps.payment.models import Payment

__all__ = ["Provider", "SIGNATURE_HEADER", "sign", "verify_signature", "parse_callback_status"]

logger = logging.getLogger("celery.tasks")

DEFAULT_TIMEOUT = 10.0
SIGNATURE_HEADER = "X-Signature"

# Статусы из callback -> внутренние статусы.
CALLBACK_STATUS_MAP = {
    "success": PaymentStatus.SUCCESS,
    "succeeded": PaymentStatus.SUCCESS,
    "failed": PaymentStatus.FAILED,
    "pending": PaymentStatus.PENDING,
}


def sign(secret: str, body: bytes) -> str:
    """HMAC-SHA256 подпись тела запроса в hex."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, body: bytes, signature: str | None) -> bool:
    """Проверяет подпись callback. Без секрета или подписи callback не принимается."""
    if not secret or not signature or not re.fullmatch(r"[0-9a-fA-F]{64}", signature.strip()):
        return False
    return hmac.compare_digest(sign(secret, body), signature.strip().lower())


def parse_callback_status(value: Any) -> PaymentStatus | None:
    return CALLBACK_STATUS_MAP.get(str(value).lower())


class Provider(ProviderBase):
    """Синхронный провайдер с оплатой через callback.

    ``create`` отправляет платёж провайдеру и сразу возвращает ``PENDING``. Итог провайдер присылает
    позже на ``callback_url`` (см. ``apps.api.payment.views.ProviderCallbackView``), тело подписано
    HMAC-SHA256 секретом ``callback_secret`` в заголовке ``X-Signature``.

    Настройки берутся из ``Provider.data``:
        base_url        - обязательный, только https, например ``https://pay.example.com/api``
        callback_secret - обязательный, секрет подписи callback
        callback_url    - необязательный; по умолчанию собирается из ``settings.BASE_URL`` и slug провайдера
        api_key         - необязательный, передаётся в ``Authorization: Bearer``
        timeout         - необязательный, секунды (по умолчанию 10)

    Эндпоинты провайдера:
        POST {base_url}/payments                      -> {"id": str, "status": str}
        GET  {base_url}/payments/{id}                 -> {"status": str}
        POST {base_url}/payments/{id}/refund          -> {"id": str, "status": str}
        POST {base_url}/payments/{id}/cancel          -> {"id": str, "status": str}
    """

    slug = "provider_b"

    def parse_callback(self, body: bytes, headers: Mapping[str, str]) -> CallbackResult:
        secret = str(self.data.get("callback_secret") or "")
        if not verify_signature(secret, body, headers.get(SIGNATURE_HEADER)):
            raise CallbackAuthenticationError

        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError
            payment_id = UUID(str(payload["order_id"]))
            payment_status = parse_callback_status(payload.get("status"))
            if payment_status is None:
                raise ValueError
        except ValueError, KeyError, TypeError, UnicodeDecodeError:
            raise CallbackPayloadError from None

        return {"payment_id": payment_id, "status": payment_status}

    def create(self, payment: Payment) -> CreatePaymentResult:
        if not self.data.get("callback_secret"):
            raise ValueError("Provider data must contain callback_secret")

        body = {
            "order_id": str(payment.pk),
            "amount": str(payment.amount),
            "callback_url": self.callback_url,
        }
        # Idempotency-Key защищает от двойного списания при повторной отправке запроса.
        data = self._request("POST", "/payments", body, idempotency_key=str(payment.pk))
        # Итог придёт в callback, поэтому сейчас платёж всегда ожидает.
        return {"id": _str_or_none(data.get("id")), "status": PaymentStatus.PENDING}

    def get_status(self, payment: Payment) -> PaymentStatus:
        data = self._request("GET", f"/payments/{_path_id(payment)}")
        return CALLBACK_STATUS_MAP.get(str(data.get("status")).lower(), PaymentStatus.FAILED)

    def make_refund(self, payment: Payment) -> RefundResult:
        data = self._request(
            "POST",
            f"/payments/{_path_id(payment)}/refund",
            {"amount": str(payment.amount)},
            idempotency_key=f"refund-{payment.pk}",
        )
        return {"id": _str_or_none(data.get("id")), "status": _refund_status(data.get("status"))}

    def cancel(self, payment: Payment) -> CancellationResult:
        data = self._request(
            "POST",
            f"/payments/{_path_id(payment)}/cancel",
            idempotency_key=f"cancel-{payment.pk}",
        )
        return {"id": _str_or_none(data.get("id")), "status": _cancellation_status(data.get("status"))}

    @property
    def callback_url(self) -> str:
        if url := self.data.get("callback_url"):
            return str(url)
        base_url = str(settings.BASE_URL or "").rstrip("/")
        return f"{base_url}/api/v1/payments/callback/{self.slug}/"

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        url = self._build_url(path)
        headers = {"Accept": "application/json"}
        if api_key := self.data.get("api_key"):
            headers["Authorization"] = f"Bearer {api_key}"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        payload = None
        if body is not None:
            payload = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"

        timeout = float(self.data.get("timeout") or DEFAULT_TIMEOUT)
        return _send(method, url, payload, headers, timeout)

    def _build_url(self, path: str) -> str:
        base_url = str(self.data.get("base_url") or "").rstrip("/")
        if parse.urlsplit(base_url).scheme != "https":
            raise ValueError("Provider data must contain https base_url")
        return f"{base_url}{path}"


def _send(method: str, url: str, payload: bytes | None, headers: dict[str, str], timeout: float) -> dict[str, Any]:
    req = request.Request(url, data=payload, headers=headers, method=method)  # noqa: S310 - схема проверена выше
    try:
        with request.urlopen(req, timeout=timeout) as response:  # noqa: S310
            raw = response.read()
    except error.HTTPError as exc:
        # Тело ответа не логируем и не пробрасываем: там могут быть чувствительные данные.
        raise RuntimeError(f"Provider responded with HTTP {exc.code} on {method} {parse.urlsplit(url).path}") from None
    except error.URLError as exc:
        raise RuntimeError(f"Provider request failed: {exc.reason}") from None

    try:
        data = json.loads(raw)
    except ValueError:
        raise RuntimeError("Provider returned invalid JSON") from None
    if not isinstance(data, dict):
        raise RuntimeError("Provider returned unexpected response")
    return data


def _path_id(payment: Payment) -> str:
    return parse.quote(str(payment.pk), safe="")


def _str_or_none(value: Any) -> str | None:
    return None if value is None else str(value)


def _refund_status(value: Any) -> RefundStatus:
    return {"refunded": RefundStatus.REFUNDED, "pending": RefundStatus.PENDING}.get(
        str(value).lower(), RefundStatus.FAILED
    )


def _cancellation_status(value: Any) -> CancellationStatus:
    return {"cancelled": CancellationStatus.CANCELLED, "pending": CancellationStatus.PENDING}.get(
        str(value).lower(), CancellationStatus.FAILED
    )
