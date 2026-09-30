package payments

import (
	"errors"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/orders"
)

var (
	ErrIdempotencyKeyReused     = errors.New("IDEMPOTENCY_KEY_REUSED")
	ErrOrderNotWaitingPayment   = errors.New("ORDER_NOT_WAITING_PAYMENT")
	ErrPaymentAttemptExists     = errors.New("PAYMENT_ATTEMPT_ALREADY_EXISTS")
	ErrPaymentPayerNotFound     = errors.New("PAYMENT_PAYER_NOT_FOUND")
	ErrPaymentProviderMismatch  = errors.New("PAYMENT_PROVIDER_MISMATCH")
	ErrPaymentProviderBadStatus = errors.New("PAYMENT_PROVIDER_INVALID_STATUS")
	ErrDesignatedPlayerNotFound = errors.New("DESIGNATED_PLAYER_NOT_FOUND")
	ErrMockProviderUnsupported  = errors.New("MOCK_PAYMENT_OPERATION_UNSUPPORTED")
	ErrPaymentProviderMissing   = errors.New("PAYMENT_PROVIDER_NOT_CONFIGURED")
)

type Preparation struct {
	Order         orders.Order
	Provider      string
	PaymentStatus string
	ClientPayload map[string]string
	Replayed      bool
}

type PrepareOutput struct {
	OrderID       string            `json:"order_id"`
	OrderStatus   string            `json:"order_status"`
	Provider      string            `json:"provider"`
	PaymentStatus string            `json:"payment_status"`
	ClientPayload map[string]string `json:"client_payload"`
	Replayed      bool              `json:"replayed"`
}

func (p Preparation) Output() PrepareOutput {
	return PrepareOutput{
		OrderID:       p.Order.ID,
		OrderStatus:   p.Order.Status,
		Provider:      p.Provider,
		PaymentStatus: p.PaymentStatus,
		ClientPayload: p.ClientPayload,
		Replayed:      p.Replayed,
	}
}
