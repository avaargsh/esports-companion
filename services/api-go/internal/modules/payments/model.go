package payments

import "errors"

var (
	ErrIdempotencyKeyReused     = errors.New("IDEMPOTENCY_KEY_REUSED")
	ErrOrderNotWaitingPayment   = errors.New("ORDER_NOT_WAITING_PAYMENT")
	ErrPaymentAttemptExists     = errors.New("PAYMENT_ATTEMPT_ALREADY_EXISTS")
	ErrPaymentPayerNotFound     = errors.New("PAYMENT_PAYER_NOT_FOUND")
	ErrPaymentProviderMismatch  = errors.New("PAYMENT_PROVIDER_MISMATCH")
	ErrPaymentProviderBadStatus = errors.New("PAYMENT_PROVIDER_INVALID_STATUS")
	ErrDesignatedPlayerNotFound = errors.New("DESIGNATED_PLAYER_NOT_FOUND")
	ErrMockProviderUnsupported  = errors.New("MOCK_PAYMENT_OPERATION_UNSUPPORTED")
)
