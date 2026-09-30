package refunds

import (
	"context"

	"github.com/avaargsh/esports-companion/services/api-go/internal/ports"
)

type ManualProvider struct{}

func (ManualProvider) Name() string {
	return "MANUAL"
}

func (ManualProvider) CreateRefund(
	_ context.Context,
	_ ports.RefundRequest,
) (ports.RefundIntent, error) {
	return ports.RefundIntent{
		Provider:   "MANUAL",
		Status:     "PENDING",
		RawPayload: map[string]any{"mode": "manual"},
	}, nil
}

func (ManualProvider) QueryRefund(
	_ context.Context,
	_ string,
) (ports.RefundIntent, error) {
	return ports.RefundIntent{
		Provider:   "MANUAL",
		Status:     "PENDING",
		RawPayload: map[string]any{"mode": "manual"},
	}, nil
}
