import hashlib
import secrets
import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import EmailVerificationCode


@dataclass(frozen=True)
class EmailCodeResult:
    email: str
    sent: bool


def normalize_email(email: str) -> str:
    value = email.strip().lower()
    if "@" not in value or value.startswith("@") or value.endswith("@"):
        raise ValueError("EMAIL_INVALID")
    return value


def hash_code(email: str, code: str, purpose: str) -> str:
    material = f"{settings.session_signing_key}:{purpose}:{email}:{code}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def create_email_code(db: Session, *, email: str, purpose: str) -> str:
    normalized = normalize_email(email)
    code = f"{secrets.randbelow(900000) + 100000}"
    now = datetime.now(timezone.utc)
    row = EmailVerificationCode(
        email=normalized,
        purpose=purpose,
        code_hash=hash_code(normalized, code, purpose),
        expires_at=now + timedelta(seconds=settings.email_code_ttl_seconds),
    )
    db.add(row)
    db.commit()
    return code


def consume_email_code(db: Session, *, email: str, purpose: str, code: str) -> None:
    normalized = normalize_email(email)
    now = datetime.now(timezone.utc)
    row = db.scalar(
        select(EmailVerificationCode)
        .where(
            EmailVerificationCode.email == normalized,
            EmailVerificationCode.purpose == purpose,
            EmailVerificationCode.code_hash == hash_code(normalized, code.strip(), purpose),
            EmailVerificationCode.consumed_at.is_(None),
        )
        .order_by(EmailVerificationCode.created_at.desc())
    )
    if not row:
        raise ValueError("EMAIL_CODE_INVALID")
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise ValueError("EMAIL_CODE_EXPIRED")
    row.consumed_at = now
    db.commit()


def send_email_code(email: str, code: str, *, purpose: str) -> None:
    if not settings.mail_host or not settings.mail_username or not settings.mail_password:
        raise ValueError("MAIL_CONFIG_MISSING")
    subject = "若水电竞验证码"
    purpose_text = "后台登录" if purpose == "ADMIN_LOGIN" else "绑定邮箱"
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr(("若水电竞", settings.mail_username))
    message["To"] = email
    message.set_content(
        f"你的若水电竞{purpose_text}验证码是：{code}\n\n"
        f"验证码 {settings.email_code_ttl_seconds // 60} 分钟内有效。若非本人操作，请忽略本邮件。",
        charset=settings.mail_default_encoding or "UTF-8",
    )
    if settings.mail_smtp_ssl_enable:
        client = smtplib.SMTP_SSL(settings.mail_host, settings.mail_port, timeout=10)
    else:
        client = smtplib.SMTP(settings.mail_host, settings.mail_port, timeout=10)
    try:
        client.set_debuglevel(1 if settings.mail_debug else 0)
        if settings.mail_smtp_auth:
            client.login(settings.mail_username, settings.mail_password)
        client.send_message(message)
    finally:
        client.quit()
