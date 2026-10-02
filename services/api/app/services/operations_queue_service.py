from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Dispute, Order, OutboxEvent, Refund, Withdrawal
from app.status_labels import COMMON_STATUS_TEXT, DISPUTE_STATUS_TEXT, ORDER_STATUS_TEXT, status_text


OUTBOX_SLA_SECONDS = 60
REFUND_SLA_SECONDS = 15 * 60
WITHDRAWAL_SLA_SECONDS = 60 * 60
DISPUTE_SLA_SECONDS = 24 * 60 * 60


def _status_label(kind: str, value: str) -> str:
    if kind == "DISPUTE":
        return status_text(value, DISPUTE_STATUS_TEXT)
    if kind == "FINISH_REQUESTED":
        return status_text(value, ORDER_STATUS_TEXT)
    return status_text(value, COMMON_STATUS_TEXT)


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


def _summary(
    db: Session,
    *,
    now: datetime,
    kind: str,
    label: str,
    model_id,
    timestamp_column,
    filters: tuple,
    sla_seconds: int,
    severity: str,
) -> dict:
    count, oldest = db.execute(
        select(func.count(model_id), func.min(timestamp_column)).where(*filters)
    ).one()
    deadline = now - timedelta(seconds=sla_seconds)
    breached = db.scalar(
        select(func.count(model_id)).where(
            *filters,
            timestamp_column.is_not(None),
            timestamp_column < deadline,
        )
    )
    return {
        "kind": kind,
        "label": label,
        "count": count or 0,
        "breachedCount": breached or 0,
        "oldestAgeSeconds": _age_seconds(now, oldest),
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

    outbox_filters = (OutboxEvent.status == "PENDING",)
    refund_filters = (
        Refund.status.in_(["PENDING", "SUBMITTING", "PROCESSING"]),
    )
    withdrawal_filters = (Withdrawal.status == "PENDING",)
    dispute_filters = (Dispute.status.in_(["OPEN", "RESOLVING"]),)
    finish_filters = (Order.status == "FINISH_REQUESTED",)

    categories = [
        _summary(
            db,
            now=effective_now,
            kind="OUTBOX",
            label="Outbox 堆积",
            model_id=OutboxEvent.id,
            timestamp_column=OutboxEvent.created_at,
            filters=outbox_filters,
            sla_seconds=OUTBOX_SLA_SECONDS,
            severity="critical",
        ),
        _summary(
            db,
            now=effective_now,
            kind="REFUND",
            label="退款处理中",
            model_id=Refund.id,
            timestamp_column=Refund.updated_at,
            filters=refund_filters,
            sla_seconds=REFUND_SLA_SECONDS,
            severity="critical",
        ),
        _summary(
            db,
            now=effective_now,
            kind="WITHDRAWAL",
            label="提现待处理",
            model_id=Withdrawal.id,
            timestamp_column=Withdrawal.created_at,
            filters=withdrawal_filters,
            sla_seconds=WITHDRAWAL_SLA_SECONDS,
            severity="warning",
        ),
        _summary(
            db,
            now=effective_now,
            kind="DISPUTE",
            label="争议待处理",
            model_id=Dispute.id,
            timestamp_column=Dispute.created_at,
            filters=dispute_filters,
            sla_seconds=DISPUTE_SLA_SECONDS,
            severity="warning",
        ),
        _summary(
            db,
            now=effective_now,
            kind="FINISH_REQUESTED",
            label="完成确认超时",
            model_id=Order.id,
            timestamp_column=Order.finish_requested_at,
            filters=finish_filters,
            sla_seconds=finish_sla,
            severity="warning",
        ),
    ]

    def overdue_rows(model, timestamp_column, filters: tuple, sla_seconds: int):
        deadline = effective_now - timedelta(seconds=sla_seconds)
        return list(
            db.scalars(
                select(model)
                .where(
                    *filters,
                    timestamp_column.is_not(None),
                    timestamp_column < deadline,
                )
                .order_by(timestamp_column.asc())
                .limit(limit_per_kind)
            )
        )

    outbox = overdue_rows(
        OutboxEvent,
        OutboxEvent.created_at,
        outbox_filters,
        OUTBOX_SLA_SECONDS,
    )
    refunds = overdue_rows(
        Refund,
        Refund.updated_at,
        refund_filters,
        REFUND_SLA_SECONDS,
    )
    withdrawals = overdue_rows(
        Withdrawal,
        Withdrawal.created_at,
        withdrawal_filters,
        WITHDRAWAL_SLA_SECONDS,
    )
    disputes = overdue_rows(
        Dispute,
        Dispute.created_at,
        dispute_filters,
        DISPUTE_SLA_SECONDS,
    )
    finish_orders = overdue_rows(
        Order,
        Order.finish_requested_at,
        finish_filters,
        finish_sla,
    )

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
        items.append(
            {
                "kind": kind,
                "severity": severity,
                "entityId": entity_id,
                "orderId": order_id,
                "status": _status_label(kind, status),
                "statusCode": status,
                "ageSeconds": _age_seconds(effective_now, timestamp),
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
