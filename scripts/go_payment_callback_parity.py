#!/usr/bin/env python3
"""Verify M4.2 signed WeChat payment callback interoperability."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

import psycopg
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from go_claim_parity import Response, call, dsn, expect


def create_order(
    go_base: str,
    customer_headers: dict[str, str],
    sku_id: str,
    label: str,
) -> dict[str, Any]:
    return expect(
        call(
            go_base,
            "/api/v1/orders",
            method="POST",
            headers=customer_headers,
            body={
                "sku_id": sku_id,
                "quantity": 1,
                "remark": label,
            },
        ),
        201,
        f"create {label}",
    ).body


def ensure_customer_openid(user_id: str) -> str:
    openid = f"callback-openid-{uuid.uuid4().hex[:16]}"
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET openid = %s WHERE id = %s::uuid",
                (openid, user_id),
            )
        connection.commit()
    return openid


def seed_pending(order: dict[str, Any], label: str) -> str:
    payment_id = str(uuid.uuid4())
    prepay_id = f"prepay-{uuid.uuid4().hex}"
    key = f"{label}-{uuid.uuid4().hex}"
    raw_payload = {
        "provider": {
            "outTradeNo": order["order_no"],
            "prepayId": prepay_id,
        },
        "clientPayload": {
            "package": f"prepay_id={prepay_id}",
            "signType": "RSA",
        },
    }
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO payment_transactions (
                    id,
                    order_id,
                    provider,
                    provider_txn_id,
                    idempotency_key,
                    amount,
                    status,
                    raw_payload
                )
                VALUES (
                    %s::uuid,
                    %s::uuid,
                    'WECHAT',
                    %s,
                    %s,
                    %s,
                    'PENDING',
                    %s::json
                )
                """,
                (
                    payment_id,
                    order["id"],
                    prepay_id,
                    key,
                    order["total_amount"],
                    json.dumps(raw_payload),
                ),
            )
        connection.commit()
    return prepay_id


def signed_callback(
    order: dict[str, Any],
    payer_openid: str,
    *,
    provider_txn_id: str,
    amount: int | None = None,
    currency: str = "CNY",
    event_id: str | None = None,
) -> tuple[dict[str, str], bytes, dict[str, Any], dict[str, Any]]:
    app_id = os.environ["WECHAT_APP_ID"]
    mch_id = os.environ["WECHAT_MCH_ID"]
    api_key = os.environ["WECHAT_PAY_API_V3_KEY"].encode()
    serial = os.environ["WECHAT_PAY_PLATFORM_CERT_SERIAL"]
    key_path = os.environ["WECHAT_TEST_PLATFORM_PRIVATE_KEY_FILE"]
    private_key = serialization.load_pem_private_key(
        open(key_path, "rb").read(),
        password=None,
    )

    resource_payload = {
        "mchid": mch_id,
        "appid": app_id,
        "out_trade_no": order["order_no"],
        "transaction_id": provider_txn_id,
        "trade_state": "SUCCESS",
        "payer": {"openid": payer_openid},
        "amount": {
            "total": order["total_amount"] if amount is None else amount,
            "currency": currency,
        },
    }
    resource_nonce = uuid.uuid4().hex[:12]
    associated = "transaction"
    plaintext = json.dumps(
        resource_payload,
        separators=(",", ":"),
    ).encode()
    encrypted = AESGCM(api_key).encrypt(
        resource_nonce.encode(),
        plaintext,
        associated.encode(),
    )
    event = {
        "id": event_id or f"event-{uuid.uuid4().hex}",
        "event_type": "TRANSACTION.SUCCESS",
        "resource_type": "encrypt-resource",
        "resource": {
            "algorithm": "AEAD_AES_256_GCM",
            "ciphertext": __import__("base64").b64encode(encrypted).decode(),
            "nonce": resource_nonce,
            "associated_data": associated,
        },
    }
    body = json.dumps(event, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    header_nonce = f"h-{uuid.uuid4().hex[:18]}"
    message = (
        timestamp.encode()
        + b"\n"
        + header_nonce.encode()
        + b"\n"
        + body
        + b"\n"
    )
    signature = __import__("base64").b64encode(
        private_key.sign(
            message,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    ).decode()
    return (
        {
            "Wechatpay-Timestamp": timestamp,
            "Wechatpay-Nonce": header_nonce,
            "Wechatpay-Signature": signature,
            "Wechatpay-Serial": serial,
            "Content-Type": "application/json",
        },
        body,
        event,
        resource_payload,
    )


def callback_call(
    base: str,
    headers: dict[str, str],
    body: bytes,
) -> Response:
    request = urllib.request.Request(
        base.rstrip("/") + "/api/v1/payments/wechat/callback",
        data=body,
        headers={"Accept": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
            return Response(response.status, json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return Response(exc.code, json.loads(raw) if raw else None)


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
                f"{label}: got={response.body!r} want={expected!r}"
            )
    else:
        if response.body.get("code") != "FAIL":
            raise AssertionError(f"{label}: missing FAIL envelope: {response.body!r}")
        if message is not None and response.body.get("message") != message:
            raise AssertionError(
                f"{label}: got={response.body!r} want message={message!r}"
            )


def verify_success(
    order: dict[str, Any],
    provider_txn_id: str,
    event: dict[str, Any],
    resource: dict[str, Any],
) -> None:
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT status, version, paid_at IS NOT NULL
                FROM orders
                WHERE id = %s::uuid
                """,
                (order["id"],),
            )
            state = cursor.fetchone()
            expected_state = ("MATCHING", order["version"] + 2, True)
            if state != expected_state:
                raise AssertionError(
                    f"callback order state got={state!r} want={expected_state!r}"
                )

            cursor.execute(
                """
                SELECT provider, provider_txn_id, amount, status, raw_payload
                FROM payment_transactions
                WHERE order_id = %s::uuid
                """,
                (order["id"],),
            )
            rows = cursor.fetchall()
            if len(rows) != 1:
                raise AssertionError(f"payment rows = {rows!r}")
            provider, txn_id, amount, status, raw_payload = rows[0]
            if (
                provider != "WECHAT"
                or txn_id != provider_txn_id
                or amount != order["total_amount"]
                or status != "SUCCESS"
            ):
                raise AssertionError(f"payment row mismatch: {rows[0]!r}")
            if raw_payload.get("callback") != event:
                raise AssertionError(
                    f"callback payload mismatch: {raw_payload.get('callback')!r}"
                )
            if raw_payload.get("verifiedResource") != resource:
                raise AssertionError(
                    "verified resource mismatch: "
                    f"{raw_payload.get('verifiedResource')!r}"
                )
            if not raw_payload.get("clientPayload", {}).get("package"):
                raise AssertionError("original client payload was not preserved")

            cursor.execute(
                """
                SELECT event_type, from_status, to_status, actor_type, payload_json
                FROM order_events
                WHERE order_id = %s::uuid
                  AND event_type IN ('PAYMENT_SUCCESS', 'ORDER_ENTERED_MATCHING')
                ORDER BY created_at, id
                """,
                (order["id"],),
            )
            events = cursor.fetchall()
            expected_events = [
                (
                    "PAYMENT_SUCCESS",
                    "WAITING_PAYMENT",
                    "PAID",
                    "PAYMENT",
                    {"provider": "WECHAT"},
                ),
                (
                    "ORDER_ENTERED_MATCHING",
                    "PAID",
                    "MATCHING",
                    "SYSTEM",
                    {},
                ),
            ]
            if events != expected_events:
                raise AssertionError(
                    f"callback evidence got={events!r} want={expected_events!r}"
                )

            cursor.execute(
                """
                SELECT event_type, payload_json
                FROM outbox_events
                WHERE aggregate_type = 'ORDER'
                  AND aggregate_id = %s
                  AND event_type IN ('PAYMENT_SUCCESS', 'ORDER_ENTERED_MATCHING')
                ORDER BY created_at, id
                """,
                (order["id"],),
            )
            outbox = cursor.fetchall()
            expected_outbox = [
                (
                    "PAYMENT_SUCCESS",
                    {
                        "orderId": order["id"],
                        "status": "PAID",
                        "provider": "WECHAT",
                    },
                ),
                (
                    "ORDER_ENTERED_MATCHING",
                    {"orderId": order["id"], "status": "MATCHING"},
                ),
            ]
            if outbox != expected_outbox:
                raise AssertionError(
                    f"callback outbox got={outbox!r} want={expected_outbox!r}"
                )


def assert_pending(order_id: str) -> None:
    with psycopg.connect(dsn()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT status FROM orders WHERE id = %s::uuid",
                (order_id,),
            )
            order_status = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT status
                FROM payment_transactions
                WHERE order_id = %s::uuid
                """,
                (order_id,),
            )
            payment_status = cursor.fetchone()[0]
    if order_status != "WAITING_PAYMENT" or payment_status != "PENDING":
        raise AssertionError(
            f"failed callback mutated state order={order_status} payment={payment_status}"
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
    customer_headers = {"X-User-Id": customer_id}
    sku_id = bootstrap["games"][0]["skus"][0]["id"]
    payer_openid = ensure_customer_openid(customer_id)

    go_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "go-wechat-callback",
    )
    seed_pending(go_order, "go-callback")
    go_txn = f"wx-go-{uuid.uuid4().hex}"
    headers, body, event, resource = signed_callback(
        go_order,
        payer_openid,
        provider_txn_id=go_txn,
    )
    assert_callback(
        callback_call(args.go_base, headers, body),
        200,
        label="Go verified callback",
    )
    verify_success(go_order, go_txn, event, resource)

    assert_callback(
        callback_call(args.python_base, headers, body),
        200,
        label="FastAPI replays Go callback",
    )
    assert_callback(
        callback_call(args.go_base, headers, body),
        200,
        label="Go replays callback",
    )
    verify_success(go_order, go_txn, event, resource)
    print("PASS Go callback + cross-runtime replay")

    py_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "python-wechat-callback",
    )
    seed_pending(py_order, "py-callback")
    py_txn = f"wx-py-{uuid.uuid4().hex}"
    py_headers, py_body, py_event, py_resource = signed_callback(
        py_order,
        payer_openid,
        provider_txn_id=py_txn,
    )
    assert_callback(
        callback_call(args.python_base, py_headers, py_body),
        200,
        label="FastAPI verified callback",
    )
    assert_callback(
        callback_call(args.go_base, py_headers, py_body),
        200,
        label="Go replays FastAPI callback",
    )
    verify_success(py_order, py_txn, py_event, py_resource)
    print("PASS FastAPI callback + Go replay")

    concurrent_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "concurrent-wechat-callback",
    )
    seed_pending(concurrent_order, "concurrent-callback")
    concurrent_txn = f"wx-concurrent-{uuid.uuid4().hex}"
    c_headers, c_body, c_event, c_resource = signed_callback(
        concurrent_order,
        payer_openid,
        provider_txn_id=concurrent_txn,
    )

    def invoke(_index: int) -> Response:
        return callback_call(args.go_base, c_headers, c_body)

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        responses = list(executor.map(invoke, range(20)))
    failures = [
        response
        for response in responses
        if response.status != 200
        or response.body != {"code": "SUCCESS", "message": "成功"}
    ]
    if failures:
        raise AssertionError(f"concurrent callback failures: {failures!r}")
    verify_success(concurrent_order, concurrent_txn, c_event, c_resource)
    print("PASS 20-way signed callback is exactly-once")

    mismatch_cases = [
        ("amount", {"amount": 1}, "PAYMENT_AMOUNT_MISMATCH"),
        ("currency", {"currency": "USD"}, "PAYMENT_CURRENCY_MISMATCH"),
        ("payer", {}, "PAYMENT_PAYER_MISMATCH"),
    ]
    for label, overrides, expected_message in mismatch_cases:
        order = create_order(
            args.go_base,
            customer_headers,
            sku_id,
            f"callback-{label}-mismatch",
        )
        seed_pending(order, f"callback-{label}")
        payer = (
            "wrong-openid"
            if label == "payer"
            else payer_openid
        )
        case_headers, case_body, _event, _resource = signed_callback(
            order,
            payer,
            provider_txn_id=f"wx-{label}-{uuid.uuid4().hex}",
            amount=(
                order["total_amount"] + 1
                if label == "amount"
                else None
            ),
            currency=overrides.get("currency", "CNY"),
        )
        for base, runtime in ((args.python_base, "FastAPI"), (args.go_base, "Go")):
            assert_callback(
                callback_call(base, case_headers, case_body),
                400,
                message=expected_message,
                label=f"{runtime} {label} mismatch",
            )
        assert_pending(order["id"])
    print("PASS amount/currency/payer callback binding parity")

    tampered_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "callback-tampered",
    )
    seed_pending(tampered_order, "callback-tampered")
    t_headers, t_body, _event, _resource = signed_callback(
        tampered_order,
        payer_openid,
        provider_txn_id=f"wx-tampered-{uuid.uuid4().hex}",
        event_id="event-original",
    )
    tampered = t_body.replace(b"event-original", b"event-tampered")
    for base, runtime in ((args.python_base, "FastAPI"), (args.go_base, "Go")):
        assert_callback(
            callback_call(base, t_headers, tampered),
            400,
            message="WECHAT_CALLBACK_SIGNATURE_INVALID",
            label=f"{runtime} tampered callback",
        )
    assert_pending(tampered_order["id"])
    print("PASS tampered callback rejected before mutation")

    reused_order = create_order(
        args.go_base,
        customer_headers,
        sku_id,
        "callback-provider-txn-reused",
    )
    seed_pending(reused_order, "callback-provider-txn-reused")
    r_headers, r_body, _event, _resource = signed_callback(
        reused_order,
        payer_openid,
        provider_txn_id=go_txn,
    )
    for base, runtime in ((args.python_base, "FastAPI"), (args.go_base, "Go")):
        assert_callback(
            callback_call(base, r_headers, r_body),
            400,
            message="PAYMENT_PROVIDER_TXN_REUSED",
            label=f"{runtime} provider txn reuse",
        )
    assert_pending(reused_order["id"])
    print("PASS provider transaction cannot bind to another order")

    print("M4.2 payment callback parity PASS")
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
    ) as exc:
        print(f"M4.2 payment callback parity FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
