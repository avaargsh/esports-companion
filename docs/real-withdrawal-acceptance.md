# Real Withdrawal Acceptance

This is the manual release acceptance for the first low-value real withdrawal.

The current payout boundary is intentionally simple:

```text
Player Mini Program
  -> request withdrawal
  -> available balance decreases
  -> frozen balance increases
  -> Withdrawal PENDING
  -> operator performs the real external payout
  -> Admin clicks Approve and records the external payout reference
  -> Withdrawal COMPLETED
  -> frozen balance decreases
  -> Ledger contains WITHDRAWAL_FROZEN + WITHDRAWAL_COMPLETED
```

The platform does **not** initiate the external payout yet. Admin approval must happen
only after the operator has verified that the real payout succeeded in the external
payment channel.

## Preconditions

Before using real money:

1. deploy staging with real WeChat login/payment credentials;
2. run `make staging-preflight`;
3. run `make staging-check BASE_URL=https://...`;
4. complete one low-value real order through payment, service completion and settlement;
5. confirm the player Mini Program shows the resulting amount as available earnings.

Do not add another auth-evidence / authority-envelope variant to prepare this test.
The current authority checks stay internal and unchanged.

## Acceptance procedure

### 1. Player requests a low-value withdrawal

In the Mini Program:

```text
My -> Player Workspace -> Earnings & Withdrawal -> Request Withdrawal
```

Use the smallest operationally meaningful amount.

Record the resulting `withdrawal_id`. The request must become `PENDING`, and the
requested amount must move from available balance to frozen balance.

### 2. Admin verifies the request

In Admin:

```text
Finance -> Withdrawal Review
```

Confirm the amount and player are the intended acceptance account.

Do **not** click Approve yet.

### 3. Perform the real external payout

Use the approved real payout method outside this application.

After the payment channel reports success, record its immutable transaction/reference
number. This is the value that must be entered into Admin.

If the external payout fails, choose Reject instead. Rejection must return the frozen
amount to available balance.

### 4. Approve only after payout success

Click **Approve** in Admin and paste the exact external payout reference.

Expected business state:

```text
Withdrawal.status        = COMPLETED
Withdrawal.provider      = MANUAL
Withdrawal.providerTxnId = <real external reference>
Wallet.frozenBalance     decreases by the withdrawal amount
Ledger                   has exactly one WITHDRAWAL_FROZEN
                         and one WITHDRAWAL_COMPLETED for this withdrawal
```

### 5. Run the read-only verifier

On the staging host:

```bash
make staging-withdrawal-acceptance \
  WITHDRAWAL_ID=<uuid> \
  PAYOUT_REF=<external-payout-reference>
```

The command reads PostgreSQL state from the running API container and performs no
mutation. A successful run exits with code 0 and prints:

```json
{
  "status": "PASS",
  "checks": {
    "statusCompleted": true,
    "payoutReferencePresent": true,
    "expectedPayoutReference": true,
    "payoutReferenceUnique": true,
    "singleFrozenLedgerEntry": true,
    "singleCompletedLedgerEntry": true,
    "frozenAmountMatches": true,
    "completionDoesNotDoubleDebit": true
  }
}
```

The report also prints the withdrawal, current wallet balances and withdrawal-scoped
ledger facts so the operator can retain the acceptance output with the release record.

## Release decision

The real-withdrawal checklist item is complete only when all three facts exist:

- the player actually received the external payout;
- Admin stores the same immutable external payout reference;
- `staging-withdrawal-acceptance` returns `PASS`.

A demo/mock withdrawal, a manually edited database row, or a `COMPLETED` status without
an external payout does not satisfy this gate.
