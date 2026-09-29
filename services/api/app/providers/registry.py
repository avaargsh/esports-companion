from app.config import settings
from app.providers.payment import MockPaymentProvider, PaymentProvider


def get_payment_provider(name: str | None = None) -> PaymentProvider:
    provider_name = (name or settings.payment_provider).strip().lower()
    if provider_name == "mock":
        return MockPaymentProvider()
    raise ValueError(f"PAYMENT_PROVIDER_NOT_CONFIGURED:{provider_name}")
