from app.config import settings
from app.providers.auth import AuthProvider, MockAuthProvider
from app.providers.payment import MockPaymentProvider, PaymentProvider


def get_payment_provider(name: str | None = None) -> PaymentProvider:
    provider_name = (name or settings.payment_provider).strip().lower()
    if provider_name == "mock":
        return MockPaymentProvider()
    raise ValueError(f"PAYMENT_PROVIDER_NOT_CONFIGURED:{provider_name}")



def get_auth_provider(name: str | None = None) -> AuthProvider:
    provider_name = (name or settings.auth_provider).strip().lower()
    if provider_name == "mock":
        return MockAuthProvider()
    raise ValueError(f"AUTH_PROVIDER_NOT_CONFIGURED:{provider_name}")
