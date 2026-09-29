# Order state machine

```text
WAITING_PAYMENT -> PAID -> MATCHING -> ACCEPTED -> IN_SERVICE
                                      -> FINISH_REQUESTED
                                      -> COMPLETED -> SETTLED
```

Exceptional paths: CANCELLED, REFUNDING -> REFUNDED, DISPUTED.

All transitions go through `OrderService.transition()`.
