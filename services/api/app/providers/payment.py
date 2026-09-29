import uuid
from dataclasses import dataclass
from typing import Literal, Protocol

from app.models import Order


PaymentStatus = Literal["PENDING", "SUCCESS"]


@dataclass(frozen=True)
class PaymentIntent:
    provider: str
    provider_txn_id: str
    status: PaymentStatus
    raw_payload: dict
    client_payload: dict


class PaymentProvider(Protocol):
    name: str

    def create_payment(
        self,
        *,
        order: Order,
        idempotency_key: str,
    ) -> PaymentIntent:
        """Create a provider-side payment attempt.

        A provider may return PENDING with client parameters (for example,
        WeChat requestPayment parameters), or SUCCESS for synchronous demo
        providers.
        """


class MockPaymentProvider:
    name = "MOCK"

    def create_payment(
        self,
        *,
        order: Order,
        idempotency_key: str,
    ) -> PaymentIntent:
        return PaymentIntent(
            provider=self.name,
            provider_txn_id=f"mock_{uuid.uuid4().hex}",
            status="SUCCESS",
            raw_payload={
                "mode": "mock",
                "idempotencyKey": idempotency_key,
            },
            client_payload={},
        )
