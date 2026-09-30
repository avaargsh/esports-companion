# Sample Product 01 — On-demand Service Marketplace

This is the first product scenario built on top of the reusable Mini Program starter.

The reference skin is esports companion, but the product shape is deliberately broader: a customer purchases a service, a provider accepts and fulfills it, money settles after confirmation, and the customer's review feeds the provider's reputation.

## Product loop

```text
Discover service
      ↓
Create order
      ↓
Pay
      ↓
Public matching pool
      ↓
Provider claim
      ↓
Start service
      ↓
Finish request
      ↓
Customer confirm
      ↓
Settlement / provider income
      ↓
Review
      ↓
Public provider reputation
      └──────────────► next customer decision
```

The scenario is intentionally narrower than the repository's release smoke suite. It answers one product question:

> Can a real marketplace transaction create value for both sides and feed the result back into the next transaction?

Disputes, refunds, designated booking, withdrawals and Admin operations remain part of the wider reference product, but are not required for Sample Product 01.

## Human demo path

Start the development stack and Mini Program:

```bash
cp .env.example .env
make up

cd apps/miniapp
npm install
npm run dev:mp-weixin
```

Then walk the product:

```text
Customer
Home
  → choose a game/service
  → create order
  → pay

Provider
Workbench
  → order pool
  → claim
  → start
  → finish

Customer
Order detail
  → confirm completion
  → submit 5-star review

Provider / next customer
Workbench shows settled income
Public provider profile shows the new review
```

Demo mode uses seeded identities and mock payment only. Real WeChat auth/payment remain staging/production acceptance boundaries.

## Automated acceptance

Run against the local API:

```bash
make sample-product-01
```

Or save machine-readable evidence explicitly:

```bash
python3 scripts/sample_product_01.py \
  --evidence /tmp/sample-product-01-evidence.json
```

The acceptance runner verifies:

1. the order follows the expected state path;
2. a paid pooled order is visible to the provider;
3. the provider can claim exactly the order being tested;
4. fulfillment reaches `SETTLED` only after customer confirmation;
5. provider wallet available balance increases by exactly `player_amount`;
6. the corresponding `PROVIDER_INCOME` ledger entry exists;
7. the submitted review becomes visible on the public provider profile;
8. the append-only order event trail covers the expected state path in order.

CI uploads the resulting evidence JSON for each commit.

## Evidence contract

The generated evidence contains:

- scenario ID and PASS status;
- actors and selected catalog item;
- order ID and full state path;
- total/provider/platform money split;
- provider wallet before/after and ledger entry;
- review ID, public visibility and provider reputation snapshot;
- observed order event types and durable `to_status` transition evidence;
- per-step acceptance results.

This makes the sample product a repeatable vertical slice rather than a screenshots-only demo.
