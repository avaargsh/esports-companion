from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.providers.auth import AuthProvider


class AuthService:
    @staticmethod
    def login_with_code(
        db: Session,
        *,
        provider: AuthProvider,
        code: str,
    ) -> tuple[User, bool]:
        identity = provider.exchange_code(code)

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
            db.commit()
            db.refresh(user)
            created = True
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
