import argparse
import json
import uuid
from datetime import datetime

from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    Dispute,
    Order,
    OrderEvent,
    PaymentTransaction,
    Refund,
    Settlement,
)


def iso(value: datetime | None):
    return value.isoformat() if value else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export redacted staging WeChat acceptance evidence."
    )
    parser.add_argument("--order-id", required=True)
    parser.add_argument(
        "--expect",
        choices=("payment", "refund"),
        default="payment",
    )
    args = parser.parse_args()

    try:
        order_id = uuid.UUID(args.order_id)
    except ValueError as exc:
        raise SystemExit("ORDER_ID_INVALID") from exc

    with SessionLocal() as db:
        order = db.get(Order, order_id)
        if not order:
            raise SystemExit("ORDER_NOT_FOUND")

        payments = list(
            db.scalars(
                select(PaymentTransaction)
                .where(PaymentTransaction.order_id == order.id)
                .order_by(PaymentTransaction.created_at, PaymentTransaction.id)
            )
        )
        events = list(
            db.scalars(
                select(OrderEvent)
                .where(OrderEvent.order_id == order.id)
                .order_by(OrderEvent.created_at, OrderEvent.id)
            )
        )
        disputes = list(
            db.scalars(
                select(Dispute)
                .where(Dispute.order_id == order.id)
                .order_by(Dispute.created_at, Dispute.id)
            )
        )
        refunds = list(
            db.scalars(
                select(Refund)
                .where(Refund.order_id == order.id)
                .order_by(Refund.created_at, Refund.id)
            )
        )
        settlement = db.scalar(
            select(Settlement).where(Settlement.order_id == order.id)
        )

        evidence = {
            "order": {
                "id": str(order.id),
                "orderNo": order.order_no,
                "status": order.status,
                "amount": order.total_amount,
                "createdAt": iso(order.created_at),
                "paidAt": iso(order.paid_at),
                "completedAt": iso(order.completed_at),
                "settledAt": iso(order.settled_at),
            },
            "payments": [
                {
                    "provider": item.provider,
                    "status": item.status,
                    "providerTransactionId": item.provider_txn_id,
                    "amount": item.amount,
                    "createdAt": iso(item.created_at),
                }
                for item in payments
            ],
            "events": [
                {
                    "type": item.event_type,
                    "from": item.from_status,
                    "to": item.to_status,
                    "actor": item.actor_type,
                    "createdAt": iso(item.created_at),
                }
                for item in events
            ],
            "disputes": [
                {
                    "id": str(item.id),
                    "status": item.status,
                    "reason": item.reason_code,
                    "resolution": item.resolution,
                    "createdAt": iso(item.created_at),
                    "resolvedAt": iso(item.resolved_at),
                }
                for item in disputes
            ],
            "refunds": [
                {
                    "id": str(item.id),
                    "provider": item.provider,
                    "status": item.status,
                    "outRefundNo": item.out_refund_no,
                    "providerRefundId": item.provider_refund_id,
                    "amount": item.amount,
                    "createdAt": iso(item.created_at),
                    "completedAt": iso(item.completed_at),
                }
                for item in refunds
            ],
            "settlement": (
                {
                    "status": settlement.status,
                    "grossAmount": settlement.gross_amount,
                    "playerAmount": settlement.player_amount,
                    "platformFee": settlement.platform_fee,
                    "createdAt": iso(settlement.created_at),
                }
                if settlement
                else None
            ),
        }

    payment_ok = any(
        item["provider"] == "WECHAT" and item["status"] == "SUCCESS"
        for item in evidence["payments"]
    )
    payment_event_ok = any(
        item["type"] == "PAYMENT_SUCCESS" for item in evidence["events"]
    )

    checks = {
        "wechatPaymentSuccess": payment_ok,
        "paymentEventPresent": payment_event_ok,
    }

    if args.expect == "refund":
        refund_ok = any(
            item["provider"] == "WECHAT" and item["status"] == "COMPLETED"
            for item in evidence["refunds"]
        )
        refund_event_ok = any(
            item["type"] == "REFUND_COMPLETED" for item in evidence["events"]
        )
        checks.update(
            {
                "wechatRefundCompleted": refund_ok,
                "refundEventPresent": refund_event_ok,
                "orderRefunded": evidence["order"]["status"] == "REFUNDED",
            }
        )

    passed = all(checks.values())
    print(
        json.dumps(
            {
                "status": "PASS" if passed else "FAIL",
                "expect": args.expect,
                "checks": checks,
                "evidence": evidence,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
