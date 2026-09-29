from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

router = APIRouter(include_in_schema=False)

HTTP_REQUESTS = Counter(
    "esports_http_requests_total",
    "HTTP requests completed by the API.",
    ["method", "route", "status"],
)
HTTP_DURATION = Histogram(
    "esports_http_request_duration_seconds",
    "HTTP request latency by stable route template.",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
HTTP_INFLIGHT = Gauge(
    "esports_http_inflight_requests",
    "HTTP requests currently executing.",
    ["method"],
)
ORDER_TRANSITIONS = Counter(
    "esports_order_transitions_total",
    "Order state transitions attempted through the domain state machine.",
    ["from_status", "to_status", "event_type"],
)
OPERATIONAL_METRICS_SCAN_SUCCESS = Gauge(
    "esports_operational_metrics_scan_success",
    "Whether the latest PostgreSQL operational metrics scan succeeded.",
)
OUTBOX_PENDING = Gauge(
    "esports_outbox_pending",
    "Pending transactional outbox events.",
)
OUTBOX_OLDEST_PENDING_SECONDS = Gauge(
    "esports_outbox_oldest_pending_seconds",
    "Age in seconds of the oldest pending outbox event.",
)
REFUNDS_INFLIGHT = Gauge(
    "esports_refunds_inflight",
    "Refunds waiting for provider completion or reconciliation.",
)
REFUNDS_OLDEST_INFLIGHT_SECONDS = Gauge(
    "esports_refunds_oldest_inflight_seconds",
    "Age in seconds of the oldest in-flight refund.",
)
WITHDRAWALS_PENDING = Gauge(
    "esports_withdrawals_pending",
    "Withdrawals waiting for completion or rejection.",
)
WITHDRAWALS_OLDEST_PENDING_SECONDS = Gauge(
    "esports_withdrawals_oldest_pending_seconds",
    "Age in seconds of the oldest pending withdrawal.",
)
DISPUTES_OPEN = Gauge(
    "esports_disputes_open",
    "Open or resolving disputes.",
)
DISPUTES_OLDEST_OPEN_SECONDS = Gauge(
    "esports_disputes_oldest_open_seconds",
    "Age in seconds of the oldest open/resolving dispute.",
)
FINISH_REQUESTS_PENDING = Gauge(
    "esports_finish_requests_pending",
    "Orders waiting for customer completion confirmation.",
)
FINISH_REQUESTS_OVERDUE = Gauge(
    "esports_finish_requests_overdue",
    "Finish requests older than the configured auto-confirm timeout plus scan grace.",
)
FINISH_REQUESTS_OLDEST_SECONDS = Gauge(
    "esports_finish_requests_oldest_seconds",
    "Age in seconds of the oldest pending finish request.",
)


def stable_route(scope: dict) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    return str(path) if path else "unmatched"


def observe_http(
    *,
    method: str,
    route: str,
    status_code: int,
    duration_seconds: float,
    trace_id: str | None = None,
) -> None:
    if route == "/metrics":
        return
    exemplar = {"trace_id": trace_id} if trace_id else None
    HTTP_REQUESTS.labels(
        method=method,
        route=route,
        status=str(status_code),
    ).inc(exemplar=exemplar)
    HTTP_DURATION.labels(
        method=method,
        route=route,
    ).observe(duration_seconds, exemplar=exemplar)


def observe_order_transition(
    *,
    from_status: str | None,
    to_status: str,
    event_type: str,
) -> None:
    ORDER_TRANSITIONS.labels(
        from_status=from_status or "NONE",
        to_status=to_status,
        event_type=event_type,
    ).inc()


@router.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
