from app.config import settings
from app.providers.auth import AuthProvider, MockAuthProvider, WeChatAuthProvider
from app.providers.payment import MockPaymentProvider, PaymentProvider, WeChatPaymentProvider
from app.providers.payment_callback import WeChatPaymentCallbackVerifier
from app.providers.refund import ManualRefundProvider, RefundProvider, WeChatRefundProvider
from app.providers.refund_callback import WeChatRefundCallbackVerifier


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



def get_wechat_callback_verifier() -> WeChatPaymentCallbackVerifier:
    return WeChatPaymentCallbackVerifier(
        api_v3_key=settings.wechat_pay_api_v3_key,
        platform_cert_serial=settings.wechat_pay_platform_cert_serial,
        platform_certificate=settings.wechat_pay_platform_certificate,
        expected_app_id=settings.wechat_app_id,
        expected_mch_id=settings.wechat_mch_id,
    )



def get_refund_provider(name: str | None = None) -> RefundProvider:
    provider_name = (name or settings.refund_provider).strip().lower()
    if provider_name == "manual":
        return ManualRefundProvider()
    if provider_name == "wechat":
        return WeChatRefundProvider(
            mch_id=settings.wechat_mch_id,
            cert_serial=settings.wechat_mch_cert_serial,
            private_key=settings.wechat_mch_private_key,
            notify_url=settings.wechat_refund_notify_url,
            api_base_url=settings.wechat_pay_api_base_url,
        )
    raise ValueError(f"REFUND_PROVIDER_NOT_CONFIGURED:{provider_name}")


def get_wechat_refund_callback_verifier() -> WeChatRefundCallbackVerifier:
    return WeChatRefundCallbackVerifier(
        api_v3_key=settings.wechat_pay_api_v3_key,
        platform_cert_serial=settings.wechat_pay_platform_cert_serial,
        platform_certificate=settings.wechat_pay_platform_certificate,
        expected_mch_id=settings.wechat_mch_id,
    )
