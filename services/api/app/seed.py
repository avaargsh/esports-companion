from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Game, ServiceSKU, User

GAMES = [
    ("wzry", "王者荣耀"),
    ("lol", "英雄联盟"),
    ("delta_force", "三角洲行动"),
    ("valorant", "无畏契约"),
]


def main():
    with SessionLocal() as db:
        if not db.scalar(select(User).limit(1)):
            db.add(User(nickname="Demo Customer", role="USER", status="ACTIVE"))
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
        user = db.scalar(select(User).limit(1))
        print(f"demo_user_id={user.id}")


if __name__ == "__main__":
    main()
