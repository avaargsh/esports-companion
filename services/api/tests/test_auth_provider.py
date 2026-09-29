from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.providers.auth import MockAuthProvider
from app.services.auth_service import AuthService


def test_mock_auth_maps_external_subject_to_stable_internal_user():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    with Session() as db:
        provider = MockAuthProvider()

        first, first_created = AuthService.login_with_code(
            db,
            provider=provider,
            code="demo-customer",
        )
        second, second_created = AuthService.login_with_code(
            db,
            provider=provider,
            code="demo-customer",
        )

        assert first.id == second.id
        assert first.openid == "mock:customer"
        assert first_created is True
        assert second_created is False
