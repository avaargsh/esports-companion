import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.order_state_machine import OrderStatus
from app.models import LedgerEntry, Order, PlayerProfile, Settlement, User, Wallet
from app.services.dispatch_service import DispatchService
from app.services.order_service import OrderService


class SettlementService:
    @staticmethod
    def _locked_wallet(db: Session, user_id: uuid.UUID) -> Wallet:
        db.execute(
            insert(Wallet)
            .values(
                id=uuid.uuid4(),
                user_id=user_id,
                available_balance=0,
                frozen_balance=0,
                version=0,
            )
            .on_conflict_do_nothing(index_elements=[Wallet.user_id])
        )
        db.flush()
        return db.scalar(
            select(Wallet)
            .where(Wallet.user_id == user_id)
            .with_for_update()
        )

    @staticmethod
    def settle(db: Session, order: Order) -> Settlement:
        existing = db.scalar(select(Settlement).where(Settlement.order_id == order.id))
        if existing:
            return existing
        if order.status != OrderStatus.COMPLETED.value:
            raise ValueError("ORDER_NOT_COMPLETED")

        assignment = DispatchService.active_assignment(db, order.id)
        player = db.get(PlayerProfile, assignment.player_id)
        if not player:
            raise LookupError("PLAYER_NOT_FOUND")
        platform_user = db.scalar(select(User).where(User.role == "PLATFORM"))
        if not platform_user:
            raise LookupError("PLATFORM_ACCOUNT_NOT_FOUND")

        player_wallet = SettlementService._locked_wallet(db, player.user_id)
        platform_wallet = SettlementService._locked_wallet(db, platform_user.id)

        settlement = Settlement(
            order_id=order.id,
            player_id=player.id,
            gross_amount=order.total_amount,
            player_amount=order.player_amount,
            platform_fee=order.platform_fee,
            status="COMPLETED",
            idempotency_key=f"order:{order.id}:settlement",
            completed_at=datetime.now(timezone.utc),
        )
        db.add(settlement)

        player_wallet.available_balance += order.player_amount
        player_wallet.version += 1
        platform_wallet.available_balance += order.platform_fee
        platform_wallet.version += 1

        db.add_all(
            [
                LedgerEntry(
                    account_id=player_wallet.id,
                    biz_type="ORDER_SETTLEMENT",
                    biz_id=str(order.id),
                    entry_type="PROVIDER_INCOME",
                    amount=order.player_amount,
                    balance_after=player_wallet.available_balance,
                ),
                LedgerEntry(
                    account_id=platform_wallet.id,
                    biz_type="ORDER_SETTLEMENT",
                    biz_id=str(order.id),
                    entry_type="PLATFORM_FEE",
                    amount=order.platform_fee,
                    balance_after=platform_wallet.available_balance,
                ),
            ]
        )

        OrderService.transition(
            db,
            order,
            OrderStatus.SETTLED,
            event_type="SETTLEMENT_COMPLETED",
            actor_type="SYSTEM",
            payload={
                "playerAmount": order.player_amount,
                "platformFee": order.platform_fee,
            },
        )
        db.commit()
        db.refresh(settlement)
        return settlement
