from app.config import settings
from app.providers.auth import AuthProvider, MockAuthProvider, WeChatAuthProvider
from app.providers.payment import MockPaymentProvider, PaymentProvider, WeChatPaymentProvider


def get_payment_provider(name: str | None = None) -> PaymentProvider:
    provider_name = (name or settings.payment_provider).strip().lower()
    if provider_name == "mock":
        return MockPaymentProvider()
    if provider_name == "wechat":
        return WeChatPaymentProvider(
            app_id=settings.wechat_app_id,
            mch_id=settings.wechat_mch_id,
            cert_serial=settings.wechat_mch_cert_serial,
            private_key=settings.wechat_mch_private_key,
            notify_url=settings.wechat_notify_url,
            api_base_url=settings.wechat_pay_api_base_url,
        )
    raise ValueError(f"PAYMENT_PROVIDER_NOT_CONFIGURED:{provider_name}")



def get_auth_provider(name: str | None = None) -> AuthProvider:
    provider_name = (name or settings.auth_provider).strip().lower()
    if provider_name == "mock":
        return MockAuthProvider()
    if provider_name == "wechat":
        return WeChatAuthProvider(
            app_id=settings.wechat_app_id,
            app_secret=settings.wechat_app_secret,
        )
    raise ValueError(f"AUTH_PROVIDER_NOT_CONFIGURED:{provider_name}")
