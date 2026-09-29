from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ExternalIdentity:
    provider: str
    subject: str
    union_id: str | None = None
    nickname: str = ""


class AuthProvider(Protocol):
    name: str

    def exchange_code(self, code: str) -> ExternalIdentity:
        """Exchange an external login code for a verified identity."""


class MockAuthProvider:
    name = "MOCK"

    _IDENTITIES = {
        "demo-customer": ExternalIdentity(
            provider="MOCK",
            subject="mock:customer",
            nickname="Demo Customer",
        ),
        "demo-player-1": ExternalIdentity(
            provider="MOCK",
            subject="mock:player:1",
            nickname="Demo Player 1",
        ),
        "demo-player-2": ExternalIdentity(
            provider="MOCK",
            subject="mock:player:2",
            nickname="Demo Player 2",
        ),
        "demo-player-3": ExternalIdentity(
            provider="MOCK",
            subject="mock:player:3",
            nickname="Demo Player 3",
        ),
    }

    def exchange_code(self, code: str) -> ExternalIdentity:
        identity = self._IDENTITIES.get(code)
        if not identity:
            raise ValueError("INVALID_MOCK_LOGIN_CODE")
        return identity
