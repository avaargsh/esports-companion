#!/usr/bin/env python3
"""Verify M4.4 refund callback and query reconciliation parity."""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import unquote
import uuid

import psycopg
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from go_claim_parity import Response, call, dsn, expect
from go_refund_submit_parity import (
    create_order,
    refund_row,
    seed_refund,
)


def platform_private_key():
    path = Path(os.environ["WECHAT_TEST_PLATFORM_PRIVATE_KEY_FILE"])
    return serialization.load_pem_private_key(path.read_bytes(), password=None)


def seed_wechat_refund(
    order: dict[str, Any],
    *,
    customer_id: str,
    admin_id: str,
    status: str = "SUBMITTING",
) -> tuple[str, str, str]:
    out_refund_no = "RFD_" + uuid.uuid4().hex
    refund_id = seed_refund(
        order,
        customer_id=customer_id,
        admin_id=admin_id,
        status=status,
        out_refund_no=out_refund_no,
    )
    payment_txn_id = "wx-pay-" + uuid.uuid4().hex
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE refunds
                SET provider = 'WECHAT',
                    raw_payload = '{"submit":{"status":"PROCESSING"}}'::json,
                    updated_at = clock_timestamp()
                WHERE id = %s::uuid
                """,
                (refund_id,),
            )
            cursor.execute(
                """
                UPDATE payment_transactions
                SET provider = 'WECHAT',
                    provider_txn_id = %s,
                    status = 'SUCCESS',
                    updated_at = clock_timestamp()
                WHERE id = (
                    SELECT id
                    FROM payment_transactions
                    WHERE order_id = %s::uuid
                    ORDER BY created_at DESC
                    LIMIT 1
                )
                """,
                (payment_txn_id, order["id"]),
            )
        connection.commit()
    return refund_id, out_refund_no, payment_txn_id


def callback_payload(
    order: dict[str, Any],
    *,
    out_refund_no: str,
    payment_txn_id: str,
    provider_refund_id: str,
    status: str = "SUCCESS",
    out_trade_no: str | None = None,
    total_amount: int | None = None,
    refund_amount: int | None = None,
) -> tuple[dict[str, str], bytes, dict[str, Any], dict[str, Any]]:
    event_type = {
        "SUCCESS": "REFUND.SUCCESS",
        "ABNORMAL": "REFUND.ABNORMAL",
        "CLOSED": "REFUND.CLOSED",
    }[status]
    resource = {
        "mchid": os.environ["WECHAT_MCH_ID"],
        "refund_id": provider_refund_id,
        "out_refund_no": out_refund_no,
        "transaction_id": payment_txn_id,
        "out_trade_no": out_trade_no or order["order_no"],
        "refund_status": status,
        "amount": {
            "total": (
                order["total_amount"]
                if total_amount is None
                else total_amount
            ),
            "refund": (
                order["total_amount"]
                if refund_amount is None
                else refund_amount
            ),
        },
    }
    plaintext = json.dumps(resource, separators=(",", ":")).encode()
    nonce = b"refund-nonce"
    associated = b"refund"
    encrypted = AESGCM(
        os.environ["WECHAT_PAY_API_V3_KEY"].encode()
    ).encrypt(nonce, plaintext, associated)
    event = {
        "id": "refund-event-" + uuid.uuid4().hex,
        "event_type": event_type,
        "resource_type": "encrypt-resource",
        "resource": {
            "algorithm": "AEAD_AES_256_GCM",
            "original_type": "refund",
            "ciphertext": base64.b64encode(encrypted).decode(),
            "nonce": nonce.decode(),
            "associated_data": associated.decode(),
        },
    }
    body = json.dumps(event, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    header_nonce = "header-" + uuid.uuid4().hex
    message = (
        timestamp.encode()
        + b"\n"
        + header_nonce.encode()
        + b"\n"
        + body
        + b"\n"
    )
    signature = platform_private_key().sign(
        message,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    headers = {
        "Wechatpay-Timestamp": timestamp,
        "Wechatpay-Nonce": header_nonce,
        "Wechatpay-Serial": os.environ[
            "WECHAT_PAY_PLATFORM_CERT_SERIAL"
        ],
        "Wechatpay-Signature": base64.b64encode(signature).decode(),
        "Content-Type": "application/json",
    }
    return headers, body, event, resource


def callback_call(
    base: str,
    headers: dict[str, str],
    body: bytes,
) -> Response:
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    request = Request(
        base.rstrip("/") + "/api/v1/refunds/wechat/callback",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            raw = response.read()
            return Response(
                response.status,
                json.loads(raw) if raw else None,
            )
    except HTTPError as exc:
        raw = exc.read()
        return Response(
            exc.code,
            json.loads(raw) if raw else None,
        )


def assert_callback(
    response: Response,
    status: int,
    *,
    message: str | None = None,
    label: str,
) -> None:
    expect(response, status, label)
    if status == 200:
        expected = {"code": "SUCCESS", "message": "成功"}
        if response.body != expected:
            raise AssertionError(
                f"{label}: body={response.body!r} want={expected!r}"
            )
        return
    if response.body.get("code") != "FAIL":
        raise AssertionError(f"{label}: missing FAIL envelope {response.body!r}")
    if message is not None and response.body.get("message") != message:
        raise AssertionError(
            f"{label}: message={response.body!r} want={message!r}"
        )


def verify_complete(
    refund_id: str,
    *,
    provider_refund_id: str,
    evidence_key: str,
) -> None:
    row = refund_row(refund_id)
    if (
        row["status"] != "COMPLETED"
        or row["provider"] != "WECHAT"
        or row["provider_refund_id"] != provider_refund_id
        or row["completed_at"] is None
    ):
        raise AssertionError(f"refund completion mismatch: {row!r}")
    if evidence_key not in row["raw_payload"]:
        raise AssertionError(
            f"refund missing {evidence_key} evidence: {row['raw_payload']!r}"
        )

    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT status
                FROM orders
                WHERE id = %s::uuid
                """,
                (row["order_id"],),
            )
            order_state = cursor.fetchone()
            if order_state != ("REFUNDED",):
                raise AssertionError(f"order state = {order_state!r}")

            cursor.execute(
                """
                SELECT status, resolution, resolved_by_user_id
                FROM disputes
                WHERE id = %s::uuid
                """,
                (row["dispute_id"],),
            )
            dispute = cursor.fetchone()
            if dispute != ("RESOLVED", "REFUND_CUSTOMER", None):
                raise AssertionError(f"dispute state = {dispute!r}")

            cursor.execute(
                """
                SELECT count(*)
                FROM order_events
                WHERE order_id = %s::uuid
                  AND event_type = 'REFUND_COMPLETED'
                """,
                (row["order_id"],),
            )
            if cursor.fetchone() != (1,):
                raise AssertionError("expected exactly one REFUND_COMPLETED event")

            cursor.execute(
                """
                SELECT count(*)
                FROM outbox_events
                WHERE aggregate_type = 'ORDER'
                  AND aggregate_id = %s
                  AND event_type = 'REFUND_COMPLETED'
                """,
                (row["order_id"],),
            )
            if cursor.fetchone() != (1,):
                raise AssertionError("expected exactly one REFUND_COMPLETED outbox")


def assert_refund_unchanged(refund_id: str, status: str = "SUBMITTING") -> None:
    row = refund_row(refund_id)
    if row["status"] != status:
        raise AssertionError(f"refund unexpectedly changed: {row!r}")
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT status FROM orders WHERE id = %s::uuid",
                (row["order_id"],),
            )
            if cursor.fetchone() != ("REFUNDING",):
                raise AssertionError("invalid callback/query mutated order")


class FakeRefundQueryServer:
    def __init__(self) -> None:
        self.private_key = platform_private_key()
        self.serial = os.environ["WECHAT_PAY_PLATFORM_CERT_SERIAL"]
        self.overrides: dict[str, dict[str, Any]] = {}
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                prefix = "/v3/refund/domestic/refunds/"
                if not self.path.startswith(prefix):
                    self.send_error(404)
                    return
                out_refund_no = unquote(self.path[len(prefix):])
                payload = outer.payload(out_refund_no)
                raw = json.dumps(payload, separators=(",", ":")).encode()
                timestamp = str(int(time.time()))
                nonce = "query-response-" + uuid.uuid4().hex
                signature = outer.private_key.sign(
                    timestamp.encode()
                    + b"\n"
                    + nonce.encode()
                    + b"\n"
                    + raw
                    + b"\n",
                    padding.PKCS1v15(),
                    hashes.SHA256(),
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Wechatpay-Timestamp", timestamp)
                self.send_header("Wechatpay-Nonce", nonce)
                self.send_header("Wechatpay-Serial", outer.serial)
                self.send_header(
                    "Wechatpay-Signature",
                    base64.b64encode(signature).decode(),
                )
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, _format: str, *_args: object) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def payload(self, out_refund_no: str) -> dict[str, Any]:
        with psycopg.connect(dsn()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        r.amount,
                        o.order_no,
                        o.total_amount,
                        p.provider_txn_id
                    FROM refunds r
                    JOIN orders o ON o.id = r.order_id
                    JOIN LATERAL (
                        SELECT provider_txn_id
                        FROM payment_transactions
                        WHERE order_id = o.id
                          AND provider = 'WECHAT'
                          AND status = 'SUCCESS'
                        ORDER BY created_at DESC
                        LIMIT 1
                    ) p ON true
                    WHERE r.out_refund_no = %s
                    """,
                    (out_refund_no,),
                )
                row = cursor.fetchone()
        if row is None:
            return {"code": "RESOURCE_NOT_EXISTS"}
        refund_amount, order_no, total_amount, txn_id = row
        payload: dict[str, Any] = {
            "refund_id": "wx-query-" + out_refund_no[-16:],
            "out_refund_no": out_refund_no,
            "transaction_id": txn_id,
            "out_trade_no": order_no,
            "status": "SUCCESS",
            "amount": {
                "total": total_amount,
                "refund": refund_amount,
                "currency": "CNY",
            },
        }
        payload.update(self.overrides.get(out_refund_no, {}))
        return payload


def ensure_go_binary() -> Path:
    target = Path("/tmp/esports-api-go")
    if target.exists():
        return target
    subprocess.run(
        ["go", "build", "-o", str(target), "./cmd/api"],
        cwd="services/api-go",
        check=True,
    )
    return target


def wait_ready(base: str) -> None:
    for _ in range(60):
        try:
            response = call(base, "/readyz")
            if response.status == 200:
                return
        except OSError:
            pass
        time.sleep(0.25)
    raise AssertionError(f"runtime did not become ready: {base}")


def start_wechat_runtimes(
    provider_base_url: str,
) -> tuple[subprocess.Popen[bytes], subprocess.Popen[bytes], Any, Any]:
    env = os.environ.copy()
    env["REFUND_PROVIDER"] = "wechat"
    env["WECHAT_PAY_API_BASE_URL"] = provider_base_url

    fastapi_log = open("/tmp/fastapi-refund-recovery.log", "wb")
    go_log = open("/tmp/go-refund-recovery.log", "wb")

    fastapi = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8001",
        ],
        cwd="services/api",
        env=env,
        stdout=fastapi_log,
        stderr=subprocess.STDOUT,
    )
    go_env = env.copy()
    go_env["API_GO_HTTP_ADDR"] = "127.0.0.1:8081"
    go = subprocess.Popen(
        [str(ensure_go_binary())],
        env=go_env,
        stdout=go_log,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_ready("http://127.0.0.1:8001")
        wait_ready("http://127.0.0.1:8081")
    except Exception:
        fastapi.terminate()
        go.terminate()
        fastapi.wait(timeout=5)
        go.wait(timeout=5)
        fastapi_log.close()
        go_log.close()
        raise
    return fastapi, go, fastapi_log, go_log


def stop_processes(
    fastapi: subprocess.Popen[bytes],
    go: subprocess.Popen[bytes],
    fastapi_log: Any,
    go_log: Any,
) -> None:
    for process in (fastapi, go):
        process.terminate()
    for process in (fastapi, go):
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    fastapi_log.close()
    go_log.close()


def reconcile(
    base: str,
    refund_id: str,
    admin_headers: dict[str, str],
) -> Response:
    return call(
        base,
        f"/api/v1/admin/refunds/{refund_id}/reconcile",
        method="POST",
        headers=admin_headers,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-base", default="http://127.0.0.1:8000")
    parser.add_argument("--go-base", default="http://127.0.0.1:8080")
    args = parser.parse_args()

    bootstrap = expect(
        call(args.python_base, "/api/v1/dev/bootstrap"),
        200,
        "bootstrap",
    ).body
    customer_id = bootstrap["customerUserId"]
    admin_id = bootstrap["adminUserId"]
    customer_headers = {"X-User-Id": customer_id}
    admin_headers = {"X-Admin-Id": admin_id}
    sku_id = bootstrap["games"][0]["skus"][0]["id"]

    # Go callback -> FastAPI replay.
    go_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "refund-callback-go",
    )
    go_refund, go_out, go_payment = seed_wechat_refund(
        go_order,
        customer_id=customer_id,
        admin_id=admin_id,
    )
    go_provider_refund = "wx-refund-" + uuid.uuid4().hex
    headers, body, _event, _resource = callback_payload(
        go_order,
        out_refund_no=go_out,
        payment_txn_id=go_payment,
        provider_refund_id=go_provider_refund,
    )
    assert_callback(
        callback_call(args.go_base, headers, body),
        200,
        label="Go refund callback",
    )
    verify_complete(
        go_refund,
        provider_refund_id=go_provider_refund,
        evidence_key="callback",
    )
    assert_callback(
        callback_call(args.python_base, headers, body),
        200,
        label="FastAPI replay Go refund callback",
    )
    verify_complete(
        go_refund,
        provider_refund_id=go_provider_refund,
        evidence_key="callback",
    )
    print("PASS Go refund callback + FastAPI replay")

    # FastAPI callback -> Go replay.
    py_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "refund-callback-python",
    )
    py_refund, py_out, py_payment = seed_wechat_refund(
        py_order,
        customer_id=customer_id,
        admin_id=admin_id,
    )
    py_provider_refund = "wx-refund-" + uuid.uuid4().hex
    headers, body, _event, _resource = callback_payload(
        py_order,
        out_refund_no=py_out,
        payment_txn_id=py_payment,
        provider_refund_id=py_provider_refund,
    )
    assert_callback(
        callback_call(args.python_base, headers, body),
        200,
        label="FastAPI refund callback",
    )
    assert_callback(
        callback_call(args.go_base, headers, body),
        200,
        label="Go replay FastAPI refund callback",
    )
    verify_complete(
        py_refund,
        provider_refund_id=py_provider_refund,
        evidence_key="callback",
    )
    print("PASS FastAPI refund callback + Go replay")

    # 20 identical callbacks settle once.
    race_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "refund-callback-race",
    )
    race_refund, race_out, race_payment = seed_wechat_refund(
        race_order,
        customer_id=customer_id,
        admin_id=admin_id,
    )
    race_provider_refund = "wx-refund-" + uuid.uuid4().hex
    race_headers, race_body, _event, _resource = callback_payload(
        race_order,
        out_refund_no=race_out,
        payment_txn_id=race_payment,
        provider_refund_id=race_provider_refund,
    )

    def callback_race(_index: int) -> Response:
        return callback_call(args.go_base, race_headers, race_body)

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        responses = list(executor.map(callback_race, range(20)))
    failures = [
        response
        for response in responses
        if response.status != 200
        or response.body != {"code": "SUCCESS", "message": "成功"}
    ]
    if failures:
        raise AssertionError(f"concurrent refund callbacks failed: {failures!r}")
    verify_complete(
        race_refund,
        provider_refund_id=race_provider_refund,
        evidence_key="callback",
    )
    print("PASS 20-way refund callback is exactly-once")

    # Tampered signature cannot mutate.
    tampered_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "refund-callback-tampered",
    )
    tampered_refund, tampered_out, tampered_payment = seed_wechat_refund(
        tampered_order,
        customer_id=customer_id,
        admin_id=admin_id,
    )
    t_headers, t_body, _event, _resource = callback_payload(
        tampered_order,
        out_refund_no=tampered_out,
        payment_txn_id=tampered_payment,
        provider_refund_id="wx-refund-" + uuid.uuid4().hex,
    )
    tampered_body = t_body.replace(b"refund-event-", b"refund-tamper-", 1)
    for base, runtime in ((args.python_base, "FastAPI"), (args.go_base, "Go")):
        assert_callback(
            callback_call(base, t_headers, tampered_body),
            400,
            message="WECHAT_REFUND_CALLBACK_SIGNATURE_INVALID",
            label=f"{runtime} tampered refund callback",
        )
    assert_refund_unchanged(tampered_refund)
    print("PASS tampered refund callback rejected before mutation")

    # Amount binding cannot be bypassed.
    mismatch_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "refund-callback-amount-mismatch",
    )
    mismatch_refund, mismatch_out, mismatch_payment = seed_wechat_refund(
        mismatch_order,
        customer_id=customer_id,
        admin_id=admin_id,
    )
    m_headers, m_body, _event, _resource = callback_payload(
        mismatch_order,
        out_refund_no=mismatch_out,
        payment_txn_id=mismatch_payment,
        provider_refund_id="wx-refund-" + uuid.uuid4().hex,
        refund_amount=mismatch_order["total_amount"] - 1,
    )
    for base, runtime in ((args.python_base, "FastAPI"), (args.go_base, "Go")):
        assert_callback(
            callback_call(base, m_headers, m_body),
            400,
            message="REFUND_AMOUNT_MISMATCH",
            label=f"{runtime} refund amount mismatch",
        )
    assert_refund_unchanged(mismatch_refund)
    print("PASS refund callback amount binding parity")

    # Non-success provider truth updates aggregate without completing order.
    abnormal_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "refund-callback-abnormal",
    )
    abnormal_refund, abnormal_out, abnormal_payment = seed_wechat_refund(
        abnormal_order,
        customer_id=customer_id,
        admin_id=admin_id,
    )
    a_provider_refund = "wx-refund-" + uuid.uuid4().hex
    a_headers, a_body, _event, _resource = callback_payload(
        abnormal_order,
        out_refund_no=abnormal_out,
        payment_txn_id=abnormal_payment,
        provider_refund_id=a_provider_refund,
        status="ABNORMAL",
    )
    assert_callback(
        callback_call(args.go_base, a_headers, a_body),
        200,
        label="Go abnormal refund callback",
    )
    abnormal_row = refund_row(abnormal_refund)
    if (
        abnormal_row["status"] != "ABNORMAL"
        or abnormal_row["provider_refund_id"] != a_provider_refund
        or abnormal_row["failure_reason"] != "PROVIDER_REFUND_ABNORMAL"
        or "callback" not in abnormal_row["raw_payload"]
    ):
        raise AssertionError(f"abnormal refund mismatch: {abnormal_row!r}")
    assert_refund_unchanged(abnormal_refund, "ABNORMAL")
    print("PASS ABNORMAL callback preserves REFUNDING order")

    # Query reconciliation through dedicated WeChat-configured runtimes.
    provider_server = FakeRefundQueryServer()
    provider_server.start()
    fastapi2 = go2 = fastapi_log = go_log = None
    try:
        fastapi2, go2, fastapi_log, go_log = start_wechat_runtimes(
            provider_server.base_url
        )
        py2 = "http://127.0.0.1:8001"
        go2_base = "http://127.0.0.1:8081"

        go_query_order = create_order(
            args.go_base,
            customer_headers,
            sku_id,
            "refund-query-go",
        )
        go_query_refund, _go_query_out, _go_query_payment = seed_wechat_refund(
            go_query_order,
            customer_id=customer_id,
            admin_id=admin_id,
        )
        go_query = expect(
            reconcile(go2_base, go_query_refund, admin_headers),
            200,
            "Go refund reconcile",
        ).body
        if go_query["status"] != "COMPLETED":
            raise AssertionError(f"Go reconcile result = {go_query!r}")
        provider_id = refund_row(go_query_refund)["provider_refund_id"]
        verify_complete(
            go_query_refund,
            provider_refund_id=provider_id,
            evidence_key="query",
        )
        py_replay = expect(
            reconcile(py2, go_query_refund, admin_headers),
            200,
            "FastAPI replay Go reconcile",
        ).body
        if py_replay != go_query:
            raise AssertionError(
                f"reconcile replay mismatch FastAPI={py_replay!r} Go={go_query!r}"
            )
        print("PASS Go query reconcile + FastAPI replay")

        py_query_order = create_order(
            args.go_base,
            customer_headers,
            sku_id,
            "refund-query-python",
        )
        py_query_refund, _py_query_out, _py_query_payment = seed_wechat_refund(
            py_query_order,
            customer_id=customer_id,
            admin_id=admin_id,
        )
        py_query = expect(
            reconcile(py2, py_query_refund, admin_headers),
            200,
            "FastAPI refund reconcile",
        ).body
        go_replay = expect(
            reconcile(go2_base, py_query_refund, admin_headers),
            200,
            "Go replay FastAPI reconcile",
        ).body
        if go_replay != py_query:
            raise AssertionError(
                f"Go reconcile replay mismatch Go={go_replay!r} FastAPI={py_query!r}"
            )
        provider_id = refund_row(py_query_refund)["provider_refund_id"]
        verify_complete(
            py_query_refund,
            provider_refund_id=provider_id,
            evidence_key="query",
        )
        print("PASS FastAPI query reconcile + Go replay")

        race_query_order = create_order(
            args.go_base,
            customer_headers,
            sku_id,
            "refund-query-race",
        )
        race_query_refund, _out, _payment = seed_wechat_refund(
            race_query_order,
            customer_id=customer_id,
            admin_id=admin_id,
        )

        def query_race(_index: int) -> Response:
            return reconcile(go2_base, race_query_refund, admin_headers)

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            query_responses = list(executor.map(query_race, range(20)))
        query_failures = [
            response
            for response in query_responses
            if response.status != 200
            or response.body.get("status") != "COMPLETED"
        ]
        if query_failures:
            raise AssertionError(
                f"concurrent refund reconcile failures: {query_failures!r}"
            )
        provider_id = refund_row(race_query_refund)["provider_refund_id"]
        verify_complete(
            race_query_refund,
            provider_refund_id=provider_id,
            evidence_key="query",
        )
        print("PASS 20-way refund reconcile is exactly-once")

        processing_order = create_order(
            args.go_base,
            customer_headers,
            sku_id,
            "refund-query-processing",
        )
        processing_refund, processing_out, _payment = seed_wechat_refund(
            processing_order,
            customer_id=customer_id,
            admin_id=admin_id,
        )
        provider_server.overrides[processing_out] = {"status": "PROCESSING"}
        go_processing = expect(
            reconcile(go2_base, processing_refund, admin_headers),
            200,
            "Go PROCESSING reconcile",
        ).body
        if go_processing["status"] != "PROCESSING":
            raise AssertionError(f"processing result = {go_processing!r}")
        assert_refund_unchanged(processing_refund, "PROCESSING")
        print("PASS PROCESSING query does not complete order")

        mismatch_query_order = create_order(
            args.go_base,
            customer_headers,
            sku_id,
            "refund-query-amount-mismatch",
        )
        mismatch_query_refund, mismatch_query_out, _payment = seed_wechat_refund(
            mismatch_query_order,
            customer_id=customer_id,
            admin_id=admin_id,
        )
        provider_server.overrides[mismatch_query_out] = {
            "amount": {
                "total": mismatch_query_order["total_amount"],
                "refund": mismatch_query_order["total_amount"] - 1,
                "currency": "CNY",
            }
        }
        for base, runtime in ((py2, "FastAPI"), (go2_base, "Go")):
            response = expect(
                reconcile(base, mismatch_query_refund, admin_headers),
                409,
                f"{runtime} query amount mismatch",
            )
            if response.body.get("detail") != "REFUND_QUERY_AMOUNT_MISMATCH":
                raise AssertionError(
                    f"{runtime} query mismatch body = {response.body!r}"
                )
        assert_refund_unchanged(mismatch_query_refund)
        print("PASS refund query amount binding parity")
    finally:
        if fastapi2 is not None:
            stop_processes(fastapi2, go2, fastapi_log, go_log)
        provider_server.close()

    print("M4.4 refund recovery parity PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        AssertionError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        psycopg.Error,
        subprocess.SubprocessError,
    ) as exc:
        print(f"M4.4 refund recovery parity FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
