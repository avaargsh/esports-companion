package payments

import (
	"context"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/orders"
	"github.com/avaargsh/esports-companion/services/api-go/internal/ports"
)

type Service struct {
	repo               Repository
	configuredProvider ports.PaymentProvider
	mockProvider       ports.PaymentProvider
}

func NewService(repo Repository, configuredProvider ports.PaymentProvider) Service {
	return Service{
		repo:               repo,
		configuredProvider: configuredProvider,
		mockProvider:       MockProvider{},
	}
}

func (s Service) PayMock(
	ctx context.Context,
	userID string,
	orderID string,
	idempotencyKey string,
) (orders.Order, error) {
	return s.repo.Pay(
		ctx,
		userID,
		orderID,
		idempotencyKey,
		s.mockProvider,
	)
}

func (s Service) Prepare(
	ctx context.Context,
	userID string,
	orderID string,
	idempotencyKey string,
) (Preparation, error) {
	return s.repo.Prepare(
		ctx,
		userID,
		orderID,
		idempotencyKey,
		s.configuredProvider,
	)
}
