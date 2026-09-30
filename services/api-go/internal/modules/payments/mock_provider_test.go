package payments

import (
	"context"
	"strings"
	"testing"

	"github.com/avaargsh/esports-companion/services/api-go/internal/ports"
)

func TestMockProviderCreatePayment(t *testing.T) {
	intent, err := (MockProvider{}).CreatePayment(
		context.Background(),
		ports.PaymentRequest{
			OrderID:        "order-id",
			OrderNo:        "ORD_TEST",
			Description:    "test",
			AmountMinor:    3000,
			Currency:       "CNY",
			IdempotencyKey: "idem-1",
		},
	)
	if err != nil {
		t.Fatal(err)
	}
	if intent.Provider != "MOCK" {
		t.Fatalf("provider = %q", intent.Provider)
	}
	if intent.Status != "SUCCESS" {
		t.Fatalf("status = %q", intent.Status)
	}
	if !strings.HasPrefix(intent.ProviderTxnID, "mock_") {
		t.Fatalf("provider txn id = %q", intent.ProviderTxnID)
	}
	if len(strings.TrimPrefix(intent.ProviderTxnID, "mock_")) != 32 {
		t.Fatalf("provider txn id = %q", intent.ProviderTxnID)
	}
	if got := intent.RawPayload["idempotencyKey"]; got != "idem-1" {
		t.Fatalf("raw idempotency key = %#v", got)
	}
	if len(intent.ClientPayload) != 0 {
		t.Fatalf("client payload = %#v", intent.ClientPayload)
	}
}
