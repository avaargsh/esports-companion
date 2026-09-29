import pytest

from app.domain.order_state_machine import InvalidOrderTransition, ensure_transition


def test_matching_can_be_accepted():
    ensure_transition("MATCHING", "ACCEPTED")


def test_non_matching_cannot_be_claimed():
    with pytest.raises(InvalidOrderTransition):
        ensure_transition("WAITING_PAYMENT", "ACCEPTED")


def test_completed_can_only_move_to_settled():
    ensure_transition("COMPLETED", "SETTLED")
    with pytest.raises(InvalidOrderTransition):
        ensure_transition("COMPLETED", "IN_SERVICE")
