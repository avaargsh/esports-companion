# Catalog and Provider Offerings

Catalog and provider capability are deliberately separate.

```text
Platform Catalog
  Game
    -> ServiceSKU
         price / duration / fee policy
              |
              v
Provider Offering
  player_id + sku_id + ACTIVE/INACTIVE
              |
              v
Dispatch eligibility
```

## Catalog Admin

PLATFORM users can manage sellable catalog definitions through:

```http
GET   /api/v1/admin/catalog/games
POST  /api/v1/admin/catalog/games
PATCH /api/v1/admin/catalog/games/{gameId}

GET   /api/v1/admin/catalog/skus
POST  /api/v1/admin/catalog/skus
PATCH /api/v1/admin/catalog/skus/{skuId}
```

Deactivating a Game prevents new orders even if a child SKU was accidentally
left ACTIVE.

## Provider Offering

An approved player explicitly declares which SKUs they can provide:

```http
GET /api/v1/player/offerings
PUT /api/v1/player/offerings/{skuId}
```

An ACTIVE offering is now a hard dispatch invariant. A player cannot claim an
order for a SKU they have not enabled.

`price_override` is stored for future direct-booking/provider-selection flows.
It does **not** change the price of an already-created or already-paid pooled
order. Open-pool order price remains the immutable SKU price captured at order
creation.

## Redis behavior

Redis order-pool membership remains only an acceleration index. Order-pool reads
filter Redis IDs against PostgreSQL using the current player's ACTIVE offerings,
so stale Redis membership cannot bypass provider eligibility.
