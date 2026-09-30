# Sample Product 01 — 7-minute Demo Script

Use this walkthrough when showing the repository to another engineer, product owner or potential adopter.

The goal is not to demo every feature. The goal is to make one marketplace loop obvious:

```text
demand -> transaction -> matching -> fulfillment -> settlement -> reputation
```

## Before the demo

```bash
cp .env.example .env
make up

cd apps/miniapp
npm install
npm run dev:mp-weixin
```

Import `apps/miniapp/dist/dev/mp-weixin` into WeChat DevTools.

For a clean repeated demo:

```bash
make db-reset
make up
```

The purple **样板体验** cards only appear in demo mode. They are intentionally hidden when the Mini Program runs with secure WeChat auth.

## 0:00 — Explain the marketplace

Open **首页**.

Show:

- four game categories;
- quick public matching vs **找大神** designated booking;
- provider cards;
- platform guarantee / settle-after-completion / in-order aftercare.

Talking point:

> The starter is not a static storefront. Its core abstraction is a two-sided service transaction with durable order state, money settlement and reputation feedback.

## 1:00 — Customer creates demand

Choose **王者荣耀** and select a service.

The seeded catalog includes both:

- **轻松陪玩 1小时**;
- **上分陪练 1小时**.

Optionally leave a natural remark such as:

```text
娱乐局，开麦，想练辅助位
```

Create the order.

Show that the order begins at `WAITING_PAYMENT`.

## 2:00 — Pay and enter matching

On **订单详情**, use the demo payment action.

After payment the order enters:

```text
MATCHING
```

Point out the order timeline and the message explaining that the order is now in the public claim pool.

Talking point:

> Client UI never directly declares a successful payment in production. Real payment success comes from verified provider facts; mock payment exists only in demo mode.

## 3:00 — Switch sides of the marketplace

Go to:

```text
我的
  -> 陪玩工作台
  -> 抢单大厅
```

The demo journey card makes this role switch explicit.

Show the provider workspace:

- available income;
- current fulfillment counters;
- order pool;
- service and skill settings.

In **抢单大厅**, find the order just created and click **立即抢单**.

Talking point:

> Public orders are matched to enabled provider offerings. Claim correctness is protected by the backend, not by hiding buttons in the UI.

## 4:00 — Fulfill the service

In **服务详情**:

1. click **开始服务**;
2. show the order chat / timeline;
3. click **申请完成**.

The order reaches:

```text
FINISH_REQUESTED
```

The provider side now explicitly tells the demonstrator to switch back to the customer.

## 5:00 — Customer releases settlement

Return to the customer's **订单详情**.

Click **确认完成**.

The order reaches:

```text
SETTLED
```

Explain the value flow:

```text
customer payment
      ↓
order settlement
      ├─ provider income
      └─ platform fee
      ↓
provider wallet + append-only ledger
```

Then submit a 5-star review with a short comment.

## 6:00 — Show the flywheel closing

Open the assigned provider from the settled order.

Show that the review is now visible on the provider's public profile.

Then return to **陪玩工作台** and show the increased available income.

Talking point:

> The transaction does not end at SETTLED. Money feeds provider economics and the review feeds marketplace reputation, which affects the next customer's choice.

That is the Sample Product 01 closed loop.

## 7:00 — Explain what is intentionally outside this demo

The repository also implements:

- designated provider booking;
- disputes;
- refunds;
- withdrawals;
- Admin operations;
- real WeChat auth/payment adapters;
- realtime/outbox;
- production deployment and observability.

Those capabilities remain in the reference product and wider release smoke suite, but are deliberately excluded from the seven-minute sample so the core product shape stays understandable.

## Machine-verifiable version

The same story has an automated acceptance path:

```bash
make sample-product-01
```

It verifies the provider storefront, order state path, matching, fulfillment, settlement, wallet/ledger value flow, review visibility and durable order-event evidence, then writes:

```text
/tmp/sample-product-01-evidence.json
```

CI runs the scenario against an isolated PostgreSQL + Redis environment and stores the evidence as a workflow artifact.
