from abc import ABC, abstractmethod
from collections.abc import Mapping
from enum import StrEnum
from typing import TYPE_CHECKING, TypedDict
from uuid import UUID


if TYPE_CHECKING:
    from apps.payment.models import Payment

__all__ = [
    "PaymentStatus",
    "RefundStatus",
    "CancellationStatus",
    "ProviderBase",
    "CreatePaymentResult",
    "RefundResult",
    "CancellationResult",
    "CallbackResult",
    "CallbackAuthenticationError",
    "CallbackPayloadError",
    "CallbackUnsupportedError",
]


class PaymentStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PENDING = "PENDING"
    FAILED = "FAILED"
    #
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"


class RefundStatus(StrEnum):
    REFUNDED = "REFUNDED"
    PENDING = "PENDING"
    FAILED = "FAILED"


class CancellationStatus(StrEnum):
    CANCELLED = "CANCELLED"
    PENDING = "PENDING"
    FAILED = "FAILED"


class CreatePaymentResult(TypedDict):
    id: str | None
    status: PaymentStatus


class RefundResult(TypedDict):
    id: str | None
    status: RefundStatus


class CancellationResult(TypedDict):
    id: str | None
    status: CancellationStatus


class CallbackResult(TypedDict):
    payment_id: UUID
    status: PaymentStatus


class CallbackAuthenticationError(Exception):
    pass


class CallbackPayloadError(Exception):
    pass


class CallbackUnsupportedError(Exception):
    pass


class ProviderBase(ABC):
    def __init__(self, data: dict | None) -> None:
        self.data = data or {}

    def parse_callback(self, body: bytes, headers: Mapping[str, str]) -> CallbackResult:
        raise CallbackUnsupportedError

    @abstractmethod
    async def create(self, payment: Payment) -> CreatePaymentResult: ...

    @abstractmethod
    async def get_status(self, payment: Payment) -> PaymentStatus: ...

    @abstractmethod
    async def make_refund(self, payment: Payment) -> RefundResult: ...

    @abstractmethod
    async def cancel(self, payment: Payment) -> CancellationResult: ...
