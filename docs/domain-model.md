# Domain model

Core entities: User, PlayerProfile, PlayerSkill, Game, ServiceSKU, ProviderOffering, Order, OrderAssignment, OrderEvent, PaymentTransaction, Wallet, LedgerEntry, Settlement, Review and OutboxEvent.

Amounts are integer fen. Orders use `version` for optimistic concurrency. Assignment history is preserved.
