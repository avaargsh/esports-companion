import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Game, LedgerEntry, Order, OutboxEvent, PlayerProfile, ServiceSKU, User, Wallet


def _admin_and_user():
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        admin = User(
            openid=f"ops-admin-{suffix}",
            nickname=f"Ops Admin {suffix}",
            role="PLATFORM",
            status="ACTIVE",
        )
        user = User(
            openid=f"ops-user-{suffix}",
            nickname=f"Ops User {suffix}",
            phone="15500001111",
            role="USER",
            status="ACTIVE",
        )
        game = Game(code=f"ops-game-{suffix}", name="Ops Game")
        db.add_all([admin, user, game])
        db.flush()
        sku = ServiceSKU(
            game_id=game.id,
            name="Ops SKU",
            service_type="ENTERTAINMENT",
            duration_minutes=60,
            price=3000,
            platform_fee_rate="0.2000",
        )
        db.add(sku)
        db.flush()
        order = Order(
            order_no=f"OPS_{suffix}",
            user_id=user.id,
            game_id=game.id,
            sku_id=sku.id,
            status="PAID",
            quantity=1,
            unit_price=3000,
            total_amount=3000,
            player_amount=2400,
            platform_fee=600,
        )
        audit = OutboxEvent(
            aggregate_type="AUDIT",
            aggregate_id=f"USER:{user.id}",
            event_type="AUTHORIZATION_DECISION",
            payload_json={
                "actorUserId": str(admin.id),
                "action": "TEST_OPERATION",
                "scope": "PLATFORM",
                "resourceType": "USER",
                "resourceId": str(user.id),
                "decision": "ALLOW",
            },
        )
        db.add_all([order, audit])
        db.commit()
        return str(admin.id), str(user.id), order.order_no


def test_admin_can_read_users_consumption_and_operation_logs():
    admin_id, user_id, order_no = _admin_and_user()
    headers = {"X-Admin-Id": admin_id}

    with TestClient(app) as client:
        users = client.get("/api/v1/admin/users", headers=headers)
        assert users.status_code == 200
        row = next(item for item in users.json() if item["id"] == user_id)
        assert row["nickname"].startswith("Ops User")
        assert row["status"] == "启用"
        assert row["statusCode"] == "ACTIVE"
        assert row["orderCount"] >= 1
        assert row["totalSpent"] >= 3000

        records = client.get(f"/api/v1/admin/users/{user_id}/consumption-records", headers=headers)
        assert records.status_code == 200
        assert any(item["orderNo"] == order_no and item["amount"] == 3000 for item in records.json())

        logs = client.get("/api/v1/admin/operation-logs", headers=headers)
        assert logs.status_code == 200
        assert any(item["actorUserId"] == admin_id and item["action"] == "TEST_OPERATION" for item in logs.json())


def test_admin_can_blacklist_user_and_audit_is_append_only():
    admin_id, user_id, _order_no = _admin_and_user()
    headers = {"X-Admin-Id": admin_id}

    with TestClient(app) as client:
        blocked = client.patch(
            f"/api/v1/admin/users/{user_id}/status",
            headers=headers,
            json={"status": "BLOCKED", "reason": "风控命中"},
        )
        assert blocked.status_code == 200
        assert blocked.json()["status"] == "已拉黑"
        assert blocked.json()["statusCode"] == "BLOCKED"

        logs = client.get("/api/v1/admin/operation-logs", headers=headers)
        assert logs.status_code == 200
        assert any(item["action"] == "USER_STATUS_UPDATE" and item["resourceId"] == user_id for item in logs.json())

        deleted = client.delete("/api/v1/admin/operation-logs", headers=headers)
        assert deleted.status_code in {404, 405}


def test_admin_can_grant_and_revoke_platform_role_with_audit_log():
    admin_id, user_id, _order_no = _admin_and_user()
    headers = {"X-Admin-Id": admin_id}

    with TestClient(app) as client:
        promoted = client.patch(
            f"/api/v1/admin/users/{user_id}/role",
            headers=headers,
            json={"role": "PLATFORM", "reason": "升级为后台管理员"},
        )
        assert promoted.status_code == 200
        assert promoted.json()["role"] == "PLATFORM"
        assert promoted.json()["roleText"] == "平台管理员"
        assert "PLATFORM" in promoted.json()["effectiveRoles"]

        demoted = client.patch(
            f"/api/v1/admin/users/{user_id}/role",
            headers=headers,
            json={"role": "USER", "reason": "撤销后台管理员权限"},
        )
        assert demoted.status_code == 200
        assert demoted.json()["role"] == "USER"
        assert demoted.json()["roleText"] == "普通用户"
        assert "PLATFORM" not in demoted.json()["effectiveRoles"]

        logs = client.get("/api/v1/admin/operation-logs", headers=headers)
        assert logs.status_code == 200
        role_logs = [
            item
            for item in logs.json()
            if item["action"] == "USER_ROLE_UPDATE" and item["resourceId"] == user_id
        ]
        assert {item["toRole"] for item in role_logs} >= {"PLATFORM", "USER"}


def test_admin_cannot_revoke_own_platform_role():
    admin_id, _user_id, _order_no = _admin_and_user()
    headers = {"X-Admin-Id": admin_id}

    with TestClient(app) as client:
        demoted = client.patch(
            f"/api/v1/admin/users/{admin_id}/role",
            headers=headers,
            json={"role": "USER", "reason": "测试撤销最后管理员"},
        )
        assert demoted.status_code == 409
        assert demoted.json()["detail"] == "SELF_PLATFORM_ROLE_REVOKE_DENIED"


def test_admin_can_suspend_restore_player_and_read_finance_ledger():
    admin_id, user_id, _order_no = _admin_and_user()
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        player_user = User(
            openid=f"ops-player-{suffix}",
            nickname=f"Ops Player {suffix}",
            role="USER",
            status="ACTIVE",
        )
        wallet_user = User(
            openid=f"ops-wallet-{suffix}",
            nickname=f"Ops Wallet {suffix}",
            role="USER",
            status="ACTIVE",
        )
        db.add_all([player_user, wallet_user])
        db.flush()
        player = PlayerProfile(
            user_id=player_user.id,
            display_name="Ops Provider",
            bio="",
            verification_status="APPROVED",
            service_status="AVAILABLE",
        )
        wallet = Wallet(user_id=wallet_user.id, available_balance=5000, frozen_balance=0)
        db.add_all([player, wallet])
        db.flush()
        ledger = LedgerEntry(
            account_id=wallet.id,
            biz_type="SETTLEMENT",
            biz_id=f"settlement-{suffix}",
            entry_type="PLAYER_INCOME",
            amount=2400,
            balance_after=5000,
        )
        db.add(ledger)
        db.commit()
        player_id = str(player.id)
        wallet_user_id = str(wallet_user.id)
        ledger_id = str(ledger.id)

    headers = {"X-Admin-Id": admin_id}
    with TestClient(app) as client:
        suspended = client.post(
            f"/api/v1/admin/players/{player_id}/suspend",
            headers=headers,
            json={"reason": "违规接单"},
        )
        assert suspended.status_code == 200
        assert suspended.json()["serviceStatusCode"] == "SUSPENDED"
        assert suspended.json()["serviceStatus"] == "已停用"

        activated = client.post(
            f"/api/v1/admin/players/{player_id}/activate",
            headers=headers,
            json={"reason": "申诉通过"},
        )
        assert activated.status_code == 200
        assert activated.json()["serviceStatusCode"] == "OFFLINE"

        ledger_rows = client.get(
            f"/api/v1/admin/ledger?biz_type=SETTLEMENT&user_id={wallet_user_id}",
            headers=headers,
        )
        assert ledger_rows.status_code == 200
        row = next(item for item in ledger_rows.json() if item["id"] == ledger_id)
        assert row["userId"] == wallet_user_id
        assert row["bizType"] == "SETTLEMENT"
        assert row["entryType"] == "PLAYER_INCOME"
        assert row["amount"] == 2400
        assert row["balanceAfter"] == 5000

        logs = client.get("/api/v1/admin/operation-logs", headers=headers)
        assert logs.status_code == 200
        actions = {item["action"] for item in logs.json() if item["resourceId"] == player_id}
        assert {"PLAYER_SUSPEND", "PLAYER_ACTIVATE"}.issubset(actions)


def test_admin_can_create_and_publish_announcement():
    admin_id, _user_id, _order_no = _admin_and_user()
    headers = {"X-Admin-Id": admin_id}

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/admin/announcements",
            headers=headers,
            json={
                "title": "测试公告",
                "content": "真实账号测试通知",
                "audience": "ALL",
                "notice_type": "SYSTEM",
            },
        )
        assert created.status_code == 201
        announcement_id = created.json()["id"]
        assert created.json()["noticeType"] == "SYSTEM"
        assert created.json()["noticeTypeText"] == "系统通知"
        assert created.json()["statusCode"] == "DRAFT"

        published = client.post(
            f"/api/v1/admin/announcements/{announcement_id}/publish",
            headers=headers,
        )
        assert published.status_code == 200
        assert published.json()["status"] == "已发布"
        assert published.json()["statusCode"] == "PUBLISHED"

        rows = client.get("/api/v1/admin/announcements", headers=headers)
        assert rows.status_code == 200
        assert any(item["id"] == announcement_id for item in rows.json())

        normal_rows = client.get("/api/v1/announcements?notice_type=NORMAL&limit=20")
        assert normal_rows.status_code == 200
        assert all(item["noticeType"] == "NORMAL" for item in normal_rows.json())
        assert all(item["id"] != announcement_id for item in normal_rows.json())

        system_rows = client.get("/api/v1/announcements?notice_type=SYSTEM&limit=20")
        assert system_rows.status_code == 200
        assert any(item["id"] == announcement_id for item in system_rows.json())
