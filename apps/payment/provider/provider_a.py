from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any
from urllib import error, parse, request

from .base import (
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

__all__ = ["Provider"]

logger = logging.getLogger("celery.tasks")

DEFAULT_TIMEOUT = 10.0

# Статусы ответа провайдера -> внутренние статусы.
PAYMENT_STATUS_MAP = {
    "success": PaymentStatus.SUCCESS,
    "succeeded": PaymentStatus.SUCCESS,
    "pending": PaymentStatus.PENDING,
    "failed": PaymentStatus.FAILED,
    "refunded": PaymentStatus.REFUNDED,
    "cancelled": PaymentStatus.CANCELLED,
}
REFUND_STATUS_MAP = {
    "refunded": RefundStatus.REFUNDED,
    "pending": RefundStatus.PENDING,
    "failed": RefundStatus.FAILED,
}
CANCELLATION_STATUS_MAP = {
    "cancelled": CancellationStatus.CANCELLED,
    "pending": CancellationStatus.PENDING,
    "failed": CancellationStatus.FAILED,
}


class Provider(ProviderBase):
    """Простой HTTP-провайдер: каждый вызов - синхронный запрос, ответ разбирается сразу.

    Настройки берутся из ``Provider.data``:
        base_url - обязательный, только https, например ``https://pay.example.com/api``
        api_key  - необязательный, передаётся в ``Authorization: Bearer``
        timeout  - необязательный, секунды (по умолчанию 10)

    Эндпоинты:
        POST {base_url}/payments                      -> {"id": str, "status": str}
        GET  {base_url}/payments/{id}                 -> {"status": str}
        POST {base_url}/payments/{id}/refund          -> {"id": str, "status": str}
        POST {base_url}/payments/{id}/cancel          -> {"id": str, "status": str}
    """

    def create(self, payment: Payment) -> CreatePaymentResult:
        body = {
            "order_id": str(payment.pk),
            "amount": str(payment.amount),
            "idempotency_key": payment.idempotency_key,
        }
        # Idempotency-Key защищает от двойного списания при повторной отправке запроса.
        data = self._request("POST", "/payments", body, idempotency_key=str(payment.pk))
        return {
            "id": _str_or_none(data.get("id")),
            "status": _map_status(data.get("status"), PAYMENT_STATUS_MAP, PaymentStatus.FAILED),
        }

    def get_status(self, payment: Payment) -> PaymentStatus:
        data = self._request("GET", f"/payments/{_path_id(payment)}")
        return _map_status(data.get("status"), PAYMENT_STATUS_MAP, PaymentStatus.FAILED)

    def make_refund(self, payment: Payment) -> RefundResult:
        data = self._request(
            "POST",
            f"/payments/{_path_id(payment)}/refund",
            {"amount": str(payment.amount)},
            idempotency_key=f"refund-{payment.pk}",
        )
        return {
            "id": _str_or_none(data.get("id")),
            "status": _map_status(data.get("status"), REFUND_STATUS_MAP, RefundStatus.FAILED),
        }

    def cancel(self, payment: Payment) -> CancellationResult:
        data = self._request(
            "POST",
            f"/payments/{_path_id(payment)}/cancel",
            idempotency_key=f"cancel-{payment.pk}",
        )
        return {
            "id": _str_or_none(data.get("id")),
            "status": _map_status(data.get("status"), CANCELLATION_STATUS_MAP, CancellationStatus.FAILED),
        }

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


def _map_status(value: Any, mapping: dict, default):
    status = mapping.get(str(value).lower())
    if status is None:
        logger.warning(f"Unknown provider status: {value!r}")
        return default
    return status
