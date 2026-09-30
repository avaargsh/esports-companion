package orders

import (
	"errors"
	"fmt"

	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/statemachine"
)

type Status string

const (
	StatusWaitingPayment   Status = "WAITING_PAYMENT"
	StatusPaid             Status = "PAID"
	StatusMatching         Status = "MATCHING"
	StatusAccepted         Status = "ACCEPTED"
	StatusInService        Status = "IN_SERVICE"
	StatusFinishRequested  Status = "FINISH_REQUESTED"
	StatusCompleted        Status = "COMPLETED"
	StatusSettled          Status = "SETTLED"
	StatusCancelled        Status = "CANCELLED"
	StatusRefunding        Status = "REFUNDING"
	StatusRefunded         Status = "REFUNDED"
	StatusDisputed         Status = "DISPUTED"
)

var (
	ErrInvalidOrderTransition = errors.New("invalid order transition")
	orderStateMachine = statemachine.New(map[Status][]Status{
		StatusWaitingPayment:  {StatusPaid, StatusCancelled},
		StatusPaid:            {StatusMatching, StatusRefunding},
		StatusMatching:        {StatusAccepted, StatusDisputed},
		StatusAccepted:        {StatusMatching, StatusInService, StatusDisputed},
		StatusInService:       {StatusFinishRequested, StatusDisputed},
		StatusFinishRequested: {StatusCompleted, StatusDisputed},
		StatusCompleted:       {StatusSettled},
		StatusDisputed:        {StatusCompleted, StatusRefunding},
		StatusRefunding:       {StatusRefunded},
	})
)

type InvalidTransitionError struct {
	From Status
	To   Status
}

func (e *InvalidTransitionError) Error() string {
	return fmt.Sprintf("%s -> %s is not allowed", e.From, e.To)
}

func (e *InvalidTransitionError) Is(target error) bool {
	return target == ErrInvalidOrderTransition
}

func requireTransition(from, to Status) error {
	if orderStateMachine.CanTransition(from, to) {
		return nil
	}
	return &InvalidTransitionError{From: from, To: to}
}
