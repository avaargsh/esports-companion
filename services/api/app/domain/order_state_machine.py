from enum import StrEnum


class OrderStatus(StrEnum):
    WAITING_PAYMENT = "WAITING_PAYMENT"
    PAID = "PAID"
    MATCHING = "MATCHING"
    ACCEPTED = "ACCEPTED"
    IN_SERVICE = "IN_SERVICE"
    FINISH_REQUESTED = "FINISH_REQUESTED"
    COMPLETED = "COMPLETED"
    SETTLED = "SETTLED"
    CANCELLED = "CANCELLED"
    REFUNDING = "REFUNDING"
    REFUNDED = "REFUNDED"
    DISPUTED = "DISPUTED"


ALLOWED_TRANSITIONS = {
    OrderStatus.WAITING_PAYMENT: {OrderStatus.PAID, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.MATCHING, OrderStatus.REFUNDING},
    OrderStatus.MATCHING: {OrderStatus.ACCEPTED, OrderStatus.DISPUTED},
    OrderStatus.ACCEPTED: {
        OrderStatus.MATCHING,
        OrderStatus.IN_SERVICE,
        OrderStatus.DISPUTED,
    },
    OrderStatus.IN_SERVICE: {OrderStatus.FINISH_REQUESTED, OrderStatus.DISPUTED},
    OrderStatus.FINISH_REQUESTED: {OrderStatus.COMPLETED, OrderStatus.DISPUTED},
    OrderStatus.COMPLETED: {OrderStatus.SETTLED},
    OrderStatus.DISPUTED: {OrderStatus.COMPLETED, OrderStatus.REFUNDING},
    OrderStatus.REFUNDING: {OrderStatus.REFUNDED},
}


class InvalidOrderTransition(ValueError):
    pass


def ensure_transition(current: str, target: str) -> None:
    current_status = OrderStatus(current)
    target_status = OrderStatus(target)
    if target_status not in ALLOWED_TRANSITIONS.get(current_status, set()):
        raise InvalidOrderTransition(f"{current_status} -> {target_status} is not allowed")
