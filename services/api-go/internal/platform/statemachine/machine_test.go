package statemachine

import (
	"errors"
	"testing"
)

func TestMachineAllowsOnlyDeclaredTransitions(t *testing.T) {
	machine := New(map[string][]string{
		"WAITING_PAYMENT": {"PAID", "CANCELLED"},
		"PAID":            {"MATCHING"},
	})

	if err := machine.Require("WAITING_PAYMENT", "PAID"); err != nil {
		t.Fatalf("expected declared transition: %v", err)
	}
	if err := machine.Require("WAITING_PAYMENT", "SETTLED"); !errors.Is(err, ErrInvalidTransition) {
		t.Fatalf("expected invalid transition error, got %v", err)
	}
	if machine.CanTransition("UNKNOWN", "PAID") {
		t.Fatal("unknown source state must fail closed")
	}
}
