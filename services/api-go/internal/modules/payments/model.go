package payments

import (
	"errors"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/orders"
)

var (
	ErrIdempotencyKeyReused             = errors.New("IDEMPOTENCY_KEY_REUSED")
	ErrOrderNotWaitingPayment           = errors.New("ORDER_NOT_WAITING_PAYMENT")
	ErrPaymentAttemptExists             = errors.New("PAYMENT_ATTEMPT_ALREADY_EXISTS")
	ErrPaymentPayerNotFound             = errors.New("PAYMENT_PAYER_NOT_FOUND")
	ErrPaymentProviderMismatch          = errors.New("PAYMENT_PROVIDER_MISMATCH")
	ErrPaymentProviderBadStatus         = errors.New("PAYMENT_PROVIDER_INVALID_STATUS")
	ErrDesignatedPlayerNotFound         = errors.New("DESIGNATED_PLAYER_NOT_FOUND")
	ErrMockProviderUnsupported          = errors.New("MOCK_PAYMENT_OPERATION_UNSUPPORTED")
	ErrPaymentProviderMissing           = errors.New("PAYMENT_PROVIDER_NOT_CONFIGURED")
	ErrWeChatPaymentCredentialsMissing  = errors.New("WECHAT_PAYMENT_CREDENTIALS_MISSING")
	ErrWeChatPayerOpenIDRequired        = errors.New("WECHAT_PAYER_OPENID_REQUIRED")
	ErrWeChatPaymentNetwork             = errors.New("WECHAT_PAYMENT_NETWORK_ERROR")
	ErrWeChatPaymentInvalidJSON         = errors.New("WECHAT_PAYMENT_INVALID_JSON")
	ErrWeChatPaymentInvalidResponse     = errors.New("WECHAT_PAYMENT_INVALID_RESPONSE")
	ErrWeChatPaymentHTTP                = errors.New("WECHAT_PAYMENT_HTTP_ERROR")
	ErrWeChatPaymentPrivateKeyInvalid   = errors.New("WECHAT_PAYMENT_PRIVATE_KEY_INVALID")
	ErrWeChatPaymentCallbackNotMigrated = errors.New("WECHAT_PAYMENT_CALLBACK_NOT_MIGRATED")
	ErrWeChatPaymentQueryNotMigrated    = errors.New("WECHAT_PAYMENT_QUERY_NOT_MIGRATED")
	ErrWeChatCallbackConfigMissing      = errors.New("WECHAT_CALLBACK_CONFIG_MISSING")
	ErrWeChatCallbackHeadersMissing     = errors.New("WECHAT_CALLBACK_HEADERS_MISSING")
	ErrWeChatCallbackSerialUnknown      = errors.New("WECHAT_CALLBACK_CERT_SERIAL_UNKNOWN")
	ErrWeChatCallbackTimestampInvalid   = errors.New("WECHAT_CALLBACK_TIMESTAMP_INVALID")
	ErrWeChatCallbackTimestampExpired   = errors.New("WECHAT_CALLBACK_TIMESTAMP_EXPIRED")
	ErrWeChatCallbackSignatureInvalid   = errors.New("WECHAT_CALLBACK_SIGNATURE_INVALID")
	ErrWeChatCallbackInvalidJSON        = errors.New("WECHAT_CALLBACK_INVALID_JSON")
	ErrWeChatCallbackResourceMissing    = errors.New("WECHAT_CALLBACK_RESOURCE_MISSING")
	ErrWeChatCallbackAlgorithmUnsupported = errors.New("WECHAT_CALLBACK_ALGORITHM_UNSUPPORTED")
	ErrWeChatCallbackResourceInvalid      = errors.New("WECHAT_CALLBACK_RESOURCE_INVALID")
	ErrWeChatCallbackDecryptFailed        = errors.New("WECHAT_CALLBACK_DECRYPT_FAILED")
	ErrWeChatCallbackEventUnsupported     = errors.New("WECHAT_CALLBACK_EVENT_UNSUPPORTED")
	ErrWeChatCallbackTradeNotSuccess      = errors.New("WECHAT_CALLBACK_TRADE_NOT_SUCCESS")
	ErrWeChatCallbackAppIDMismatch        = errors.New("WECHAT_CALLBACK_APPID_MISMATCH")
	ErrWeChatCallbackMchIDMismatch        = errors.New("WECHAT_CALLBACK_MCHID_MISMATCH")
	ErrWeChatCallbackAmountInvalid        = errors.New("WECHAT_CALLBACK_AMOUNT_INVALID")
	ErrWeChatCallbackIdentifiersMissing   = errors.New("WECHAT_CALLBACK_IDENTIFIERS_MISSING")
	ErrPaymentOrderNotFound                = errors.New("PAYMENT_ORDER_NOT_FOUND")
	ErrPaymentAmountMismatch               = errors.New("PAYMENT_AMOUNT_MISMATCH")
	ErrPaymentCurrencyMismatch             = errors.New("PAYMENT_CURRENCY_MISMATCH")
	ErrPaymentPayerMismatch                = errors.New("PAYMENT_PAYER_MISMATCH")
	ErrPaymentProviderTxnReused            = errors.New("PAYMENT_PROVIDER_TXN_REUSED")
	ErrPaymentPendingTransactionNotFound   = errors.New("PAYMENT_PENDING_TRANSACTION_NOT_FOUND")
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
