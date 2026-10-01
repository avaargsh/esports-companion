package statemachine

import (
	"errors"
	"fmt"
)

var ErrInvalidTransition = errors.New("invalid state transition")

type Machine[S comparable] struct {
	rules map[S]map[S]struct{}
}

func New[S comparable](rules map[S][]S) Machine[S] {
	compiled := make(map[S]map[S]struct{}, len(rules))
	for from, targets := range rules {
		next := make(map[S]struct{}, len(targets))
		for _, to := range targets {
			next[to] = struct{}{}
		}
		compiled[from] = next
	}
	return Machine[S]{rules: compiled}
}

func (m Machine[S]) CanTransition(from, to S) bool {
	targets, ok := m.rules[from]
	if !ok {
		return false
	}
	_, ok = targets[to]
	return ok
}

func (m Machine[S]) Require(from, to S) error {
	if m.CanTransition(from, to) {
		return nil
	}
	return fmt.Errorf("%w: %v -> %v", ErrInvalidTransition, from, to)
}
