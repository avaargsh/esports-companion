from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User
from app.providers.auth import AuthProvider, ExternalIdentity


class AuthService:
    @staticmethod
    def login_with_code(
        db: Session,
        *,
        provider: AuthProvider,
        code: str,
    ) -> tuple[User, bool]:
        identity = provider.exchange_code(code)
        return AuthService.login_with_identity(db, identity=identity)

    @staticmethod
    def login_with_identity(
        db: Session,
        *,
        identity: ExternalIdentity,
    ) -> tuple[User, bool]:
        user = db.scalar(
            select(User).where(User.openid == identity.subject)
        )
        created = False

        if not user:
            user = User(
                openid=identity.subject,
                unionid=identity.union_id,
                nickname=identity.nickname,
                role="USER",
                status="ACTIVE",
            )
            db.add(user)
            try:
                db.commit()
                db.refresh(user)
                created = True
            except IntegrityError:
                # Another login for the same provider identity may win the
                # unique(openid) race between our SELECT and INSERT.
                db.rollback()
                user = db.scalar(
                    select(User).where(User.openid == identity.subject)
                )
                if not user:
                    raise
                created = False
        else:
            changed = False
            if identity.union_id and user.unionid != identity.union_id:
                user.unionid = identity.union_id
                changed = True
            if identity.nickname and not user.nickname:
                user.nickname = identity.nickname
                changed = True
            if changed:
                db.commit()

        return user, created
