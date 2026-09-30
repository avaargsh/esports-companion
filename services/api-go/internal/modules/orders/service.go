package orders

import (
	"context"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/auth"
)

type Service struct {
	repo Repository
}

func NewService(repo Repository) Service {
	return Service{repo: repo}
}

func (s Service) ListForUser(ctx context.Context, userID string, limit int) ([]Order, error) {
	return s.repo.ListForUser(ctx, userID, limit)
}

func (s Service) DetailForViewer(
	ctx context.Context,
	orderID string,
	principal auth.Principal,
	requestID string,
) (Detail, error) {
	order, err := s.repo.Get(ctx, orderID)
	if err != nil {
		return Detail{}, err
	}
	if _, err := s.repo.AuthorizeViewer(ctx, order, principal, requestID); err != nil {
		return Detail{}, err
	}
	return s.repo.Detail(ctx, order)
}

func (s Service) EventsForViewer(
	ctx context.Context,
	orderID string,
	principal auth.Principal,
	requestID string,
) ([]Event, error) {
	order, err := s.repo.Get(ctx, orderID)
	if err != nil {
		return nil, err
	}
	if _, err := s.repo.AuthorizeViewer(ctx, order, principal, requestID); err != nil {
		return nil, err
	}
	return s.repo.Events(ctx, order.ID)
}

func (s Service) Create(
	ctx context.Context,
	userID string,
	input CreateInput,
) (Order, error) {
	if (input.SKUID == nil) == (input.OfferingID == nil) {
		return Order{}, ErrExactlyOneSKUOrOffering
	}
	return s.repo.Create(ctx, userID, input)
}

func (s Service) Claim(
	ctx context.Context,
	userID string,
	orderID string,
	input ClaimInput,
) (Order, error) {
	return s.repo.Claim(ctx, userID, orderID, input.ExpectedVersion)
}

func (s Service) Start(
	ctx context.Context,
	userID string,
	orderID string,
) (Order, error) {
	return s.repo.TransitionAssignedPlayer(
		ctx,
		userID,
		orderID,
		StatusInService,
		"SERVICE_STARTED",
	)
}

func (s Service) Finish(
	ctx context.Context,
	userID string,
	orderID string,
) (Order, error) {
	return s.repo.TransitionAssignedPlayer(
		ctx,
		userID,
		orderID,
		StatusFinishRequested,
		"FINISH_REQUESTED",
	)
}
