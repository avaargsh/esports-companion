# WeChat Mini Program Frontend Design v0.5

## Product shell

One Mini Program, two workspaces:

- **Customer**: Home / Orders / Profile.
- **Player**: a secondary operational workspace entered from Profile.

The two roles share identity and deployment, but do not compete for the same
top-level navigation.

## Customer home

Home exposes exactly two primary intents:

```text
One-click Arrangement
  -> choose game/service
  -> marketplace matching

Find Player
  -> browse verified available players
  -> choose service
  -> designated order
```

The old "I am a player" home action is removed from the customer acquisition
surface and moved to Profile.

## Customer journey

```text
Home
 -> Game/Service OR Player/Service
 -> Create
 -> Pay
 -> Order Detail
 -> Service
 -> Confirm or Aftercare
 -> Settled / Refunded
 -> Review
```

Aftercare, refund, chat/evidence and completion remain order-detail concerns.
They do not become independent customer navigation.

## Find Player

Filtering is intentionally limited to **game** in the default UI. Rank and other
attributes can still be shown as trust signals, but they do not create a second
filter hierarchy in v0.5.

## Player journey

```text
Profile -> Player Workbench
        -> Claim
        -> Service Orders
        -> Earnings / Withdrawal
        -> My Services (collapsed configuration)
```

The workbench defaults to operational information. Offering and skill
configuration are hidden behind "My Services" until requested.

## State contract

The frontend does not invent a second order state machine. All status labels and
actions derive from backend order state and permissions.

WebSocket events remain invalidation signals; the client reloads canonical
order state from the API.

## Design rule

**Keep correctness, remove cognitive load.**

Backend concepts such as Settlement, Ledger, Dispute, Refund, Outbox and
Evidence remain durable infrastructure. They should only surface when the user
needs an action or explanation.


## First-use identity

A newly logged-in WeChat user starts as a customer. The Profile page does not
show a player workbench until a real PlayerProfile has been approved.

The player onboarding stays inside Profile:

```text
Profile
 -> Apply as Player
 -> PENDING review
 -> APPROVED
 -> Player Workbench appears
```

This avoids a separate onboarding tab/page and prevents ordinary customers from
entering a workspace for which they have no PlayerProfile.

In secure WeChat mode, client role discovery reads `/auth/me` so an operator
approval becomes visible without relying on stale roles stored in the original
login response.
