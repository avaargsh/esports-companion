package payments

import (
	"context"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/orders"
	"github.com/avaargsh/esports-companion/services/api-go/internal/ports"
)

type Service struct {
	repo         Repository
	mockProvider ports.PaymentProvider
}

func NewService(repo Repository) Service {
	return Service{
		repo:         repo,
		mockProvider: MockProvider{},
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
