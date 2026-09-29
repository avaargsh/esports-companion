# Product Simplification v0.5

The project deliberately keeps backend correctness while reducing product
surface area.

## User mental model

The customer should only need five concepts:

```text
Game -> Player -> Service -> Order -> Profile
```

The default customer path is:

```text
Home
  -> Quick Match: choose game/service -> order -> marketplace matching
  -> Find Player: choose player/service -> designated order
  -> Order Detail: status, contact, completion and aftercare
```

Top-level Mini Program tabs stay:

```text
Home / Orders / Profile
```

Discovery is a browsing mode, not a fourth product pillar. Aftercare, refunds,
evidence and messaging remain inside the order context.

## Player mental model

The player workspace is reduced to:

```text
Claim -> Fulfill -> Earnings
```

The default screen shows availability, active fulfillment, order actions and
earnings. Offering and skill configuration are collapsed under **My Services**.
Withdrawal lives under earnings rather than as a top-level product concept.

## Operator mental model

The Admin console has five top-level domains:

```text
Overview
Orders
Players
Finance
Configuration
```

Existing operational capabilities are retained but nested:

- Overview: SLA operations queue + high-level marketplace metrics.
- Orders: order list + aftercare/refund + evidence drawer.
- Players: player review + skill verification.
- Finance: withdrawals + settlements/ledger evidence.
- Configuration: games and service SKUs.

This replaces the previous nine-entry navigation without deleting the durable
backend capabilities.

## What remains internal

These are implementation/correctness concepts, not primary navigation:

```text
PaymentTransaction
OrderAssignment
OrderEvent
Settlement
LedgerEntry
Dispute
Refund
Withdrawal
Outbox
Evidence
OpenTelemetry
Prometheus
Backup/Restore
```

They stay because they protect transaction correctness and operability.

## Explicit non-goals

v0.5 does not add:

- social feed;
- voice rooms;
- following/fans;
- gifts or intimacy levels;
- clubs/guilds;
- promoters/agents;
- coupons/membership growth systems;
- CMS/banner operations;
- multi-channel commerce;
- complex dispatch roles.

The open-source value proposition remains: clone the project, understand the
transaction path quickly, and adapt the domain without first learning a large
ERP.
