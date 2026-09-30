package orders

import (
	"errors"
	"testing"
)

func TestOrderStateMachineMatchesReference(t *testing.T) {
	allowed := []struct {
		from Status
		to   Status
	}{
		{StatusWaitingPayment, StatusPaid},
		{StatusWaitingPayment, StatusCancelled},
		{StatusPaid, StatusMatching},
		{StatusPaid, StatusRefunding},
		{StatusMatching, StatusAccepted},
		{StatusMatching, StatusDisputed},
		{StatusAccepted, StatusMatching},
		{StatusAccepted, StatusInService},
		{StatusAccepted, StatusDisputed},
		{StatusInService, StatusFinishRequested},
		{StatusInService, StatusDisputed},
		{StatusFinishRequested, StatusCompleted},
		{StatusFinishRequested, StatusDisputed},
		{StatusCompleted, StatusSettled},
		{StatusDisputed, StatusCompleted},
		{StatusDisputed, StatusRefunding},
		{StatusRefunding, StatusRefunded},
	}
	for _, tc := range allowed {
		if err := requireTransition(tc.from, tc.to); err != nil {
			t.Fatalf("expected %s -> %s to be allowed: %v", tc.from, tc.to, err)
		}
	}

	for _, tc := range []struct {
		from Status
		to   Status
	}{
		{StatusAccepted, StatusFinishRequested},
		{StatusFinishRequested, StatusInService},
		{StatusSettled, StatusInService},
	} {
		err := requireTransition(tc.from, tc.to)
		if !errors.Is(err, ErrInvalidOrderTransition) {
			t.Fatalf("expected invalid transition %s -> %s, got %v", tc.from, tc.to, err)
		}
		if got, want := err.Error(), string(tc.from)+" -> "+string(tc.to)+" is not allowed"; got != want {
			t.Fatalf("error = %q, want %q", got, want)
		}
	}
}
