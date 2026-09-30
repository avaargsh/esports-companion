package payments

import (
	"context"
	"strings"
	"testing"
)

func TestMockProviderCreatePayment(t *testing.T) {
	intent, err := (MockProvider{}).CreatePayment(
		context.Background(),
		"order-id",
		3000,
		"CNY",
		"idem-1",
		"",
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
	if len(intent.ClientPayload) != 0 {
		t.Fatalf("client payload = %#v", intent.ClientPayload)
	}
}
