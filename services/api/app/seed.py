from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Game, PlayerProfile, ServiceSKU, User


GAMES = [
    ("wzry", "王者荣耀"),
    ("lol", "英雄联盟"),
    ("delta_force", "三角洲行动"),
    ("valorant", "无畏契约"),
]


def main():
    with SessionLocal() as db:
        platform = db.scalar(select(User).where(User.role == "PLATFORM"))
        if not platform:
            platform = User(nickname="Platform", role="PLATFORM", status="ACTIVE")
            db.add(platform)
            db.flush()

        customer = db.scalar(select(User).where(User.nickname == "Demo Customer"))
        if not customer:
            customer = User(
                openid="mock:customer",
                nickname="Demo Customer",
                role="USER",
                status="ACTIVE",
            )
            db.add(customer)
            db.flush()
        elif not customer.openid:
            customer.openid = "mock:customer"

        demo_players = []
        for index in range(3):
            nickname = f"Demo Player {index + 1}"
            user = db.scalar(select(User).where(User.nickname == nickname))
            if not user:
                user = User(
                    openid=f"mock:player:{index + 1}",
                    nickname=nickname,
                    role="USER",
                    status="ACTIVE",
                )
                db.add(user)
                db.flush()
            elif not user.openid:
                user.openid = f"mock:player:{index + 1}"
            profile = db.scalar(
                select(PlayerProfile).where(PlayerProfile.user_id == user.id)
            )
            if not profile:
                profile = PlayerProfile(
                    user_id=user.id,
                    display_name=nickname,
                    verification_status="APPROVED",
                    service_status="AVAILABLE",
                )
                db.add(profile)
                db.flush()
            demo_players.append((user, profile))

        for index, (code, name) in enumerate(GAMES):
            game = db.scalar(select(Game).where(Game.code == code))
            if not game:
                game = Game(code=code, name=name, sort_order=index)
                db.add(game)
                db.flush()
            sku = db.scalar(
                select(ServiceSKU).where(
                    ServiceSKU.game_id == game.id,
                    ServiceSKU.service_type == "ENTERTAINMENT",
                )
            )
            if not sku:
                db.add(
                    ServiceSKU(
                        game_id=game.id,
                        name=f"{name} 娱乐陪玩 1小时",
                        service_type="ENTERTAINMENT",
                        duration_minutes=60,
                        price=3000,
                        platform_fee_rate=Decimal("0.2000"),
                    )
                )
        db.commit()
        customer = db.scalar(select(User).where(User.nickname == "Demo Customer"))
        print(f"demo_user_id={customer.id}")
        print(f"demo_admin_id={platform.id}")
        for user, profile in demo_players:
            print(f"demo_player_user_id={user.id} player_profile_id={profile.id}")


if __name__ == "__main__":
    main()
