# Admin Information Architecture

The admin console is an **operations product**, not a database browser.

Its top-level navigation is organized around operator jobs:

```text
Overview
Orders
  - Order list
  - Aftercare / disputes / refunds
Players
  - Player review
  - Skill review
Finance
  - Withdrawals
  - Settlements
Configuration
  - Games
  - Service catalog / offerings
```

This borrows the useful information-architecture pattern from mature commerce
admin products such as CRMEB while deliberately keeping the surface much smaller.

## Ownership rules

### Overview

Answers: "What needs attention now?"

It may aggregate metrics and queues, but should not become a second copy of
every operational table.

### Orders

The order is the transaction entry point. Payment, fulfillment, communication,
evidence and aftercare remain attached to the order context.

Do not create separate top-level navigation for internal entities such as:

- assignments;
- order events;
- payment transactions;
- ledger rows.

Those are evidence/audit facts surfaced from the relevant order or finance flow.

### Players

Owns marketplace supply governance:

- player application review;
- skill certification;
- later, service/offering quality operations if required.

### Finance

Owns money movement that requires operator attention:

- withdrawals;
- settlements;
- reconciliation/evidence when needed.

Ledger remains an accounting fact, not a primary navigation destination.

### Configuration

Owns product configuration rather than daily operations:

- games;
- SKUs / service definitions;
- provider offerings and future controlled configuration.

## Component boundary

`App.vue` owns:

- operator session shell;
- top-level section selection;
- shared dataset refresh;
- cross-workspace evidence drawer.

Operational workspace components own their local sub-navigation and presentation:

- `DashboardWorkspace.vue`
- `OrdersWorkspace.vue`
- `PlayersWorkspace.vue`
- `FinanceWorkspace.vue`

Do not add a router, global state library or generic admin framework until URL
addressability or cross-page state creates a real need. This keeps the admin
small and complete instead of reproducing a large commerce platform.
