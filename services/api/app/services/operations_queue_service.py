from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Dispute, Order, OutboxEvent, Refund, Withdrawal


OUTBOX_SLA_SECONDS = 60
REFUND_SLA_SECONDS = 15 * 60
WITHDRAWAL_SLA_SECONDS = 60 * 60
DISPUTE_SLA_SECONDS = 24 * 60 * 60


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _age_seconds(now: datetime, value: datetime | None) -> int:
    normalized = _as_utc(value)
    if normalized is None:
        return 0
    return max(0, int((now - normalized).total_seconds()))


def _category(
    *,
    now: datetime,
    kind: str,
    label: str,
    rows: list,
    timestamp,
    sla_seconds: int,
    severity: str,
) -> dict:
    ages = [_age_seconds(now, timestamp(row)) for row in rows]
    return {
        "kind": kind,
        "label": label,
        "count": len(rows),
        "breachedCount": sum(age > sla_seconds for age in ages),
        "oldestAgeSeconds": max(ages, default=0),
        "slaSeconds": sla_seconds,
        "severity": severity,
    }


def build_operations_queue(
    db: Session,
    *,
    now: datetime | None = None,
    limit_per_kind: int = 50,
) -> dict:
    effective_now = now or datetime.now(timezone.utc)
    finish_sla = max(
        1,
        settings.finish_confirm_timeout_seconds + settings.order_timeout_scan_seconds,
    )

    outbox = list(
        db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.status == "PENDING")
            .order_by(OutboxEvent.created_at.asc())
            .limit(limit_per_kind)
        )
    )
    refunds = list(
        db.scalars(
            select(Refund)
            .where(Refund.status.in_(["PENDING", "SUBMITTING", "PROCESSING"]))
            .order_by(Refund.updated_at.asc())
            .limit(limit_per_kind)
        )
    )
    withdrawals = list(
        db.scalars(
            select(Withdrawal)
            .where(Withdrawal.status == "PENDING")
            .order_by(Withdrawal.created_at.asc())
            .limit(limit_per_kind)
        )
    )
    disputes = list(
        db.scalars(
            select(Dispute)
            .where(Dispute.status.in_(["OPEN", "RESOLVING"]))
            .order_by(Dispute.created_at.asc())
            .limit(limit_per_kind)
        )
    )
    finish_orders = list(
        db.scalars(
            select(Order)
            .where(Order.status == "FINISH_REQUESTED")
            .order_by(Order.finish_requested_at.asc())
            .limit(limit_per_kind)
        )
    )

    categories = [
        _category(
            now=effective_now,
            kind="OUTBOX",
            label="Outbox 堆积",
            rows=outbox,
            timestamp=lambda row: row.created_at,
            sla_seconds=OUTBOX_SLA_SECONDS,
            severity="critical",
        ),
        _category(
            now=effective_now,
            kind="REFUND",
            label="退款处理中",
            rows=refunds,
            timestamp=lambda row: row.updated_at,
            sla_seconds=REFUND_SLA_SECONDS,
            severity="critical",
        ),
        _category(
            now=effective_now,
            kind="WITHDRAWAL",
            label="提现待处理",
            rows=withdrawals,
            timestamp=lambda row: row.created_at,
            sla_seconds=WITHDRAWAL_SLA_SECONDS,
            severity="warning",
        ),
        _category(
            now=effective_now,
            kind="DISPUTE",
            label="争议待处理",
            rows=disputes,
            timestamp=lambda row: row.created_at,
            sla_seconds=DISPUTE_SLA_SECONDS,
            severity="warning",
        ),
        _category(
            now=effective_now,
            kind="FINISH_REQUESTED",
            label="完成确认超时",
            rows=finish_orders,
            timestamp=lambda row: row.finish_requested_at,
            sla_seconds=finish_sla,
            severity="warning",
        ),
    ]

    items: list[dict] = []

    def add_item(
        *,
        kind: str,
        severity: str,
        entity_id: str,
        order_id: str | None,
        status: str,
        timestamp: datetime | None,
        sla_seconds: int,
        title: str,
        detail: str,
    ) -> None:
        age = _age_seconds(effective_now, timestamp)
        if age <= sla_seconds:
            return
        items.append(
            {
                "kind": kind,
                "severity": severity,
                "entityId": entity_id,
                "orderId": order_id,
                "status": status,
                "ageSeconds": age,
                "slaSeconds": sla_seconds,
                "createdAt": timestamp,
                "title": title,
                "detail": detail,
            }
        )

    for row in outbox:
        add_item(
            kind="OUTBOX",
            severity="critical",
            entity_id=str(row.id),
            order_id=row.aggregate_id if row.aggregate_type == "ORDER" else None,
            status=row.status,
            timestamp=row.created_at,
            sla_seconds=OUTBOX_SLA_SECONDS,
            title="事务 Outbox 发布超时",
            detail=f"{row.event_type} · {row.aggregate_type}:{row.aggregate_id}",
        )

    for row in refunds:
        add_item(
            kind="REFUND",
            severity="critical",
            entity_id=str(row.id),
            order_id=str(row.order_id),
            status=row.status,
            timestamp=row.updated_at,
            sla_seconds=REFUND_SLA_SECONDS,
            title="退款 Provider 状态长时间未收敛",
            detail=f"{row.provider} · {row.out_refund_no or row.id}",
        )

    for row in withdrawals:
        add_item(
            kind="WITHDRAWAL",
            severity="warning",
            entity_id=str(row.id),
            order_id=None,
            status=row.status,
            timestamp=row.created_at,
            sla_seconds=WITHDRAWAL_SLA_SECONDS,
            title="提现等待人工处理",
            detail=f"{row.provider} · ¥{row.amount / 100:.2f}",
        )

    for row in disputes:
        add_item(
            kind="DISPUTE",
            severity="warning",
            entity_id=str(row.id),
            order_id=str(row.order_id),
            status=row.status,
            timestamp=row.created_at,
            sla_seconds=DISPUTE_SLA_SECONDS,
            title="争议超过处理 SLA",
            detail=f"{row.reason_code} · held ¥{row.held_amount / 100:.2f}",
        )

    for row in finish_orders:
        add_item(
            kind="FINISH_REQUESTED",
            severity="warning",
            entity_id=str(row.id),
            order_id=str(row.id),
            status=row.status,
            timestamp=row.finish_requested_at,
            sla_seconds=finish_sla,
            title="完成确认未被自动确认",
            detail=f"{row.order_no} · expected auto-confirm after {finish_sla}s",
        )

    severity_rank = {"critical": 0, "warning": 1}
    items.sort(
        key=lambda item: (
            severity_rank.get(item["severity"], 9),
            -(item["ageSeconds"] / max(item["slaSeconds"], 1)),
        )
    )

    return {
        "generatedAt": effective_now,
        "categories": categories,
        "items": items,
    }
