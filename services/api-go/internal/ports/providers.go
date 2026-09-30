package ports

import (
	"context"
	"time"
)

type Identity struct {
	Provider   string
	Subject    string
	UnionID    string
	Nickname   string
	SessionKey string
}

type AuthProvider interface {
	Name() string
	ExchangeCode(ctx context.Context, code string) (Identity, error)
}

type PaymentRequest struct {
	OrderID        string
	OrderNo        string
	Description    string
	AmountMinor    int64
	Currency       string
	IdempotencyKey string
	PayerSubject   string
}

type PaymentIntent struct {
	Provider      string
	ProviderTxnID string
	Status        string
	RawPayload    map[string]any
	ClientPayload map[string]string
}

type PaymentCallback struct {
	Provider      string
	ProviderTxnID string
	OrderNo       string
	PayerSubject  string
	Currency      string
	AmountMinor   int64
	PaidAt        time.Time
	RawEvent      map[string]any
	Resource      map[string]any
}

type PaymentProvider interface {
	Name() string
	CreatePayment(ctx context.Context, request PaymentRequest) (PaymentIntent, error)
	VerifyCallback(ctx context.Context, headers map[string]string, body []byte) (PaymentCallback, error)
	QueryPayment(ctx context.Context, providerTxnID string) (PaymentCallback, error)
}

type RefundIntent struct {
	Provider         string
	ProviderRefundID string
	Status           string
}

type RefundProvider interface {
	CreateRefund(
		ctx context.Context,
		paymentTxnID string,
		amountMinor int64,
		currency string,
		idempotencyKey string,
	) (RefundIntent, error)

	QueryRefund(ctx context.Context, providerRefundID string) (RefundIntent, error)
}
