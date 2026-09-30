package payments

import (
	"context"
	"strings"

	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/idgen"
	"github.com/avaargsh/esports-companion/services/api-go/internal/ports"
)

type MockProvider struct{}

func (MockProvider) CreatePayment(
	_ context.Context,
	_ string,
	_ int64,
	_ string,
	_ string,
	_ string,
) (ports.PaymentIntent, error) {
	value, err := idgen.UUIDv4()
	if err != nil {
		return ports.PaymentIntent{}, err
	}
	return ports.PaymentIntent{
		Provider:      "MOCK",
		ProviderTxnID: "mock_" + strings.ReplaceAll(value, "-", ""),
		Status:        "SUCCESS",
		ClientPayload: map[string]string{},
	}, nil
}

func (MockProvider) VerifyCallback(
	_ context.Context,
	_ map[string]string,
	_ []byte,
) (ports.PaymentCallback, error) {
	return ports.PaymentCallback{}, ErrMockProviderUnsupported
}

func (MockProvider) QueryPayment(
	_ context.Context,
	_ string,
) (ports.PaymentCallback, error) {
	return ports.PaymentCallback{}, ErrMockProviderUnsupported
}
