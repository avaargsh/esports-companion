import json
import logging
import time
import uuid

from fastapi import Request
from opentelemetry import propagate, trace
from opentelemetry.trace import SpanKind, Status, StatusCode
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.metrics import HTTP_INFLIGHT, observe_http, stable_route

tracer = trace.get_tracer("esports_companion.http")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": int(time.time() * 1000),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": settings.service_name,
            "environment": settings.app_env,
            "commit": settings.commit_sha,
        }
        for field in (
            "request_id",
            "method",
            "path",
            "status_code",
            "latency_ms",
            "trace_id",
            "span_id",
            "traceparent",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.handlers.clear()
    root.addHandler(handler)


def _trace_ids(span) -> tuple[str | None, str | None]:
    context = span.get_span_context()
    if not context.is_valid:
        return None, None
    return f"{context.trace_id:032x}", f"{context.span_id:016x}"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        request.state.request_id = request_id
        method = request.method
        started = time.perf_counter()
        logger = logging.getLogger("http.request")
        HTTP_INFLIGHT.labels(method=method).inc()

        parent_context = propagate.extract(carrier=request.headers)
        with tracer.start_as_current_span(
            f"HTTP {method}",
            context=parent_context,
            kind=SpanKind.SERVER,
        ) as span:
            try:
                response = await call_next(request)
            except Exception:
                duration_seconds = time.perf_counter() - started
                route = stable_route(request.scope)
                trace_id, span_id = _trace_ids(span)
                observe_http(
                    method=method,
                    route=route,
                    status_code=500,
                    duration_seconds=duration_seconds,
                    trace_id=trace_id,
                )
                span.update_name(f"{method} {route}")
                span.set_attribute("http.request.method", method)
                span.set_attribute("http.route", route)
                span.set_attribute("http.response.status_code", 500)
                span.set_status(Status(StatusCode.ERROR))
                logger.exception(
                    "request failed",
                    extra={
                        "request_id": request_id,
                        "method": method,
                        "path": route,
                        "status_code": 500,
                        "latency_ms": round(duration_seconds * 1000, 2),
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "traceparent": request.headers.get("traceparent"),
                    },
                )
                raise
            finally:
                HTTP_INFLIGHT.labels(method=method).dec()

            duration_seconds = time.perf_counter() - started
            route = stable_route(request.scope)
            trace_id, span_id = _trace_ids(span)
            observe_http(
                method=method,
                route=route,
                status_code=response.status_code,
                duration_seconds=duration_seconds,
                trace_id=trace_id,
            )

            span.update_name(f"{method} {route}")
            span.set_attribute("http.request.method", method)
            span.set_attribute("http.route", route)
            span.set_attribute("http.response.status_code", response.status_code)
            if response.status_code >= 500:
                span.set_status(Status(StatusCode.ERROR))

            response.headers["X-Request-Id"] = request_id
            logger.info(
                "request completed",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": route,
                    "status_code": response.status_code,
                    "latency_ms": round(duration_seconds * 1000, 2),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "traceparent": request.headers.get("traceparent"),
                },
            )
            return response
