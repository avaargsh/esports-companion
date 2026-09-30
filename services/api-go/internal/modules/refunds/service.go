package refunds

import (
	"context"

	"github.com/avaargsh/esports-companion/services/api-go/internal/ports"
)

type Service struct {
	repo     Repository
	provider ports.RefundProvider
}

func NewService(repo Repository, provider ports.RefundProvider) Service {
	return Service{repo: repo, provider: provider}
}

func (s Service) Submit(
	ctx context.Context,
	refundID string,
) (Refund, error) {
	return s.repo.Submit(ctx, refundID, s.provider)
}

func (s Service) Reconcile(
	ctx context.Context,
	refundID string,
) (Refund, error) {
	return s.repo.Reconcile(ctx, refundID, s.provider)
}

func (s Service) ApplyVerifiedCallback(
	ctx context.Context,
	callback VerifiedRefundCallback,
) (Refund, error) {
	return s.repo.ApplyVerifiedCallback(ctx, callback)
}
