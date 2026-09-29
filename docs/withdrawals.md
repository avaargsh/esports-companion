# Withdrawals

v0.2 adds a conservative withdrawal workflow on top of the existing wallet and
ledger.

```text
Player available balance
  -> request withdrawal
  -> available -amount
  -> frozen +amount
  -> PENDING
       | complete
       v
     frozen -amount
     COMPLETED

       | reject
       v
     frozen -amount
     available +amount
     REJECTED
```

## Invariants

- withdrawal amount must be positive;
- only an authenticated PLAYER may request;
- the wallet row is locked during mutation;
- available balance cannot become negative;
- request uses an `Idempotency-Key`;
- duplicate request does not freeze balance twice;
- complete/reject are idempotent;
- every balance movement writes a LedgerEntry.

## API

Player:

```http
POST /api/v1/withdrawals
Idempotency-Key: ...

GET /api/v1/withdrawals
```

Platform operations:

```http
GET  /api/v1/admin/withdrawals
POST /api/v1/admin/withdrawals/{id}/complete
Content-Type: application/json

{"provider_txn_id":"real-external-payout-reference"}

POST /api/v1/admin/withdrawals/{id}/reject
```

The v0.2 backend uses a manual/platform completion boundary. A real WeChat
Merchant Transfer adapter can replace the completion action later without
changing Wallet or Ledger semantics.


## Manual payout evidence

A MANUAL withdrawal is not complete merely because an operator clicked a button.

The completion endpoint requires the real external payout/transfer reference. The
reference is persisted as `provider_txn_id` and is immutable once the
withdrawal reaches `COMPLETED`. Retrying completion with the same reference is
idempotent; a conflicting reference is rejected.
