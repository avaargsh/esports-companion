from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    Game,
    PlayerProfile,
    PlayerSkill,
    ProviderOffering,
    ServiceSKU,
    User,
)


GAMES = [
    ("wzry", "王者荣耀"),
    ("lol", "英雄联盟"),
    ("delta_force", "三角洲行动"),
    ("valorant", "无畏契约"),
]

DEMO_PLAYERS = [
    {
        "display_name": "小鹿",
        "bio": "声音温柔，偏娱乐陪玩和新手友好局。可开麦，节奏轻松，不压力上分。",
        "ranks": {
            "wzry": "荣耀王者",
            "lol": "钻石",
            "delta_force": "烽火熟练",
            "valorant": "超凡",
        },
    },
    {
        "display_name": "阿策",
        "bio": "主打上分陪练和复盘，沟通直接。擅长把一局里的关键决策讲清楚。",
        "ranks": {
            "wzry": "百星王者",
            "lol": "大师",
            "delta_force": "机密熟练",
            "valorant": "神话",
        },
    },
    {
        "display_name": "南星",
        "bio": "偏团队氛围和双排体验，熟悉多位置补位。适合晚间娱乐局和固定车队。",
        "ranks": {
            "wzry": "荣耀王者",
            "lol": "翡翠",
            "delta_force": "全面战场熟练",
            "valorant": "钻石",
        },
    },
]

SERVICE_TEMPLATES = [
    {
        "service_type": "ENTERTAINMENT",
        "name": "轻松陪玩 1小时",
        "duration_minutes": 60,
        "price": 3000,
    },
    {
        "service_type": "COACHING",
        "name": "上分陪练 1小时",
        "duration_minutes": 60,
        "price": 4500,
    },
]


def main():
    with SessionLocal() as db:
        platform = db.scalar(select(User).where(User.role == "PLATFORM"))
        if not platform:
            platform = User(
                openid="mock:platform",
                nickname="Platform",
                role="PLATFORM",
                status="ACTIVE",
            )
            db.add(platform)
            db.flush()
        elif not platform.openid:
            platform.openid = "mock:platform"

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
        for index, demo in enumerate(DEMO_PLAYERS):
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
                    display_name=demo["display_name"],
                    bio=demo["bio"],
                    verification_status="APPROVED",
                    service_status="AVAILABLE",
                )
                db.add(profile)
                db.flush()
            else:
                profile.display_name = demo["display_name"]
                profile.bio = demo["bio"]
                profile.verification_status = "APPROVED"
                profile.service_status = "AVAILABLE"
            demo_players.append((user, profile, demo))

        games_by_code = {}
        for index, (code, name) in enumerate(GAMES):
            game = db.scalar(select(Game).where(Game.code == code))
            if not game:
                game = Game(code=code, name=name, sort_order=index)
                db.add(game)
                db.flush()
            else:
                game.name = name
                game.sort_order = index
                game.status = "ACTIVE"
            games_by_code[code] = game

            for template in SERVICE_TEMPLATES:
                sku = db.scalar(
                    select(ServiceSKU).where(
                        ServiceSKU.game_id == game.id,
                        ServiceSKU.service_type == template["service_type"],
                    )
                )
                name_with_game = f"{name} · {template['name']}"
                if not sku:
                    sku = ServiceSKU(
                        game_id=game.id,
                        name=name_with_game,
                        service_type=template["service_type"],
                        duration_minutes=template["duration_minutes"],
                        price=template["price"],
                        platform_fee_rate=Decimal("0.2000"),
                    )
                    db.add(sku)
                else:
                    sku.name = name_with_game
                    sku.duration_minutes = template["duration_minutes"]
                    sku.price = template["price"]
                    sku.platform_fee_rate = Decimal("0.2000")
                    sku.status = "ACTIVE"
        db.flush()

        all_skus = list(
            db.scalars(select(ServiceSKU).where(ServiceSKU.status == "ACTIVE"))
        )
        for _user, profile, demo in demo_players:
            for code, game in games_by_code.items():
                skill = db.scalar(
                    select(PlayerSkill).where(
                        PlayerSkill.player_id == profile.id,
                        PlayerSkill.game_id == game.id,
                    )
                )
                if not skill:
                    skill = PlayerSkill(
                        player_id=profile.id,
                        game_id=game.id,
                        rank=demo["ranks"][code],
                        description="Demo verified skill",
                        verification_status="APPROVED",
                        status="ACTIVE",
                    )
                    db.add(skill)
                else:
                    skill.rank = demo["ranks"][code]
                    skill.description = "平台样板数据 · 已审核技能"
                    skill.verification_status = "APPROVED"
                    skill.status = "ACTIVE"

            for sku in all_skus:
                existing = db.scalar(
                    select(ProviderOffering).where(
                        ProviderOffering.player_id == profile.id,
                        ProviderOffering.sku_id == sku.id,
                    )
                )
                description = (
                    "轻松开麦，按你的节奏玩，适合娱乐局和新手体验。"
                    if sku.service_type == "ENTERTAINMENT"
                    else "边打边讲关键决策，适合想稳定提升和复盘的玩家。"
                )
                if not existing:
                    db.add(
                        ProviderOffering(
                            player_id=profile.id,
                            sku_id=sku.id,
                            description=description,
                            status="ACTIVE",
                        )
                    )
                else:
                    existing.description = description
                    existing.status = "ACTIVE"

        db.commit()
        customer = db.scalar(select(User).where(User.nickname == "Demo Customer"))
        print(f"demo_user_id={customer.id}")
        print(f"demo_admin_id={platform.id}")
        for user, profile, _demo in demo_players:
            print(f"demo_player_user_id={user.id} player_profile_id={profile.id}")


if __name__ == "__main__":
    main()
