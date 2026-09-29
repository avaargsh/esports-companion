# Disputes and Refunds

v0.2 disputes are deliberately limited to **pre-settlement** orders.

Eligible states:

```text
ACCEPTED
IN_SERVICE
FINISH_REQUESTED
```

Opening a dispute moves the order to `DISPUTED`. This is the fund hold:
provider settlement stops, and the auto-confirm worker no longer sees the order.

Resolution paths:

```text
DISPUTED -- release provider --> COMPLETED --> SETTLED
DISPUTED -- refund customer --> REFUNDING --> REFUNDED
```

A `Dispute` stores the held order amount and audit metadata. A separate
`Refund` aggregate records refund lifecycle and idempotency.

The first implementation uses a manual refund completion boundary. A future
`WeChatRefundProvider` should replace only the external refund execution,
while the dispute/order state machine remains unchanged.

Already-settled disputes and clawbacks are intentionally out of scope for this
slice because they require provider-wallet reversal and negative-balance policy.
