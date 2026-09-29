# WeChat Refund Adapter

The dispute domain remains provider-neutral. A refund approval moves the order
to `REFUNDING` and creates a durable `Refund`; the provider adapter performs
the external side effect.

With `REFUND_PROVIDER=wechat`, the backend calls
`POST /v3/refund/domestic/refunds` using the original successful WeChat
`transaction_id`, a persisted stable `out_refund_no`, and integer-cent
amounts. `WECHAT_REFUND_NOTIFY_URL` points to
`/api/v1/refunds/wechat/callback`.

The provider response may be `PROCESSING`; that does not finish the order.
Only a verified `REFUND.SUCCESS` callback can finalize
`Refund COMPLETED -> Order REFUNDED -> Dispute RESOLVED`.

Callback processing verifies the exact raw body using the `Wechatpay-*`
headers, decrypts the resource using APIv3 AES-256-GCM, and validates merchant,
original transaction, merchant order, merchant refund number, and amounts.

`REFUND.ABNORMAL` and `REFUND.CLOSED` are persisted for operator handling.
Development keeps `REFUND_PROVIDER=manual` so the local Golden Slice does not
require live WeChat credentials.
