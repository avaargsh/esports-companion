# MVP milestones

The project is feature-complete enough for the reference marketplace flow. New
work should optimize simplicity, adoption and production verification rather
than add more product modules.

| Milestone | Definition of done |
|---|---|
| M0 | FastAPI + PostgreSQL + Redis + migrations + tests + CI |
| M1 | Game/service -> create order -> pay -> marketplace matching |
| M2 | Provider -> atomic claim -> service lifecycle |
| M3 | Settlement/ledger -> review -> realtime -> Admin -> Mini Program |
| M4 | WeChat auth/payment/refund + session/RBAC + disputes/withdrawals |
| M5 | Production readiness: backup/restore, ingress, metrics/traces, alerts, staging gate |
| M6 | Product simplification: Home/Orders/Profile, Player Claim/Fulfill/Earnings, Admin 5-domain navigation |

## Freeze line

Do not add a new top-level product module unless it is required to complete one
of these existing user jobs:

```text
Customer: find service -> order -> receive service -> aftercare
Player:   claim -> fulfill -> earn
Operator: orders -> players -> finance -> configuration
```

Backend correctness primitives may evolve without becoming new navigation
concepts.
