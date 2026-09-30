package refunds

import (
	"errors"

	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/httpx"
)

var (
	ErrRefundNotFound                 = errors.New("REFUND_NOT_FOUND")
	ErrRefundNotSubmittable           = errors.New("REFUND_NOT_SUBMITTABLE")
	ErrOrderNotRefunding              = errors.New("ORDER_NOT_REFUNDING")
	ErrSuccessfulPaymentNotFound      = errors.New("SUCCESSFUL_PAYMENT_NOT_FOUND")
	ErrRefundProviderMismatch         = errors.New("REFUND_PROVIDER_MISMATCH")
	ErrRefundProviderMissing          = errors.New("REFUND_PROVIDER_NOT_CONFIGURED")
	ErrWeChatRefundCredentialsMissing = errors.New("WECHAT_REFUND_CREDENTIALS_MISSING")
	ErrWeChatRefundRequiresPayment    = errors.New("WECHAT_REFUND_REQUIRES_SUCCESSFUL_WECHAT_PAYMENT")
	ErrWeChatPaymentTxnMissing        = errors.New("WECHAT_PAYMENT_TRANSACTION_ID_MISSING")
	ErrRefundOutRefundNoMissing       = errors.New("REFUND_OUT_REFUND_NO_MISSING")
	ErrWeChatRefundNetwork            = errors.New("WECHAT_REFUND_NETWORK_ERROR")
	ErrWeChatRefundInvalidJSON        = errors.New("WECHAT_REFUND_INVALID_JSON")
	ErrWeChatRefundInvalidResponse    = errors.New("WECHAT_REFUND_INVALID_RESPONSE")
	ErrWeChatRefundStatusInvalid      = errors.New("WECHAT_REFUND_STATUS_INVALID")
	ErrWeChatRefundHTTP               = errors.New("WECHAT_REFUND_HTTP_ERROR")
	ErrWeChatRefundSignatureHeaders   = errors.New("WECHAT_REFUND_RESPONSE_SIGNATURE_HEADERS_MISSING")
	ErrWeChatRefundSerialUnknown      = errors.New("WECHAT_REFUND_RESPONSE_CERT_SERIAL_UNKNOWN")
	ErrWeChatRefundSignatureInvalid   = errors.New("WECHAT_REFUND_RESPONSE_SIGNATURE_INVALID")
	ErrWeChatRefundPrivateKeyInvalid  = errors.New("WECHAT_REFUND_PRIVATE_KEY_INVALID")
	ErrWeChatRefundCertificateInvalid = errors.New("WECHAT_REFUND_CERTIFICATE_INVALID")
	ErrWeChatRefundQueryNotMigrated   = errors.New("WECHAT_REFUND_QUERY_NOT_MIGRATED")
)

type Refund struct {
	ID               string          `json:"id"`
	OrderID          string          `json:"order_id"`
	DisputeID        string          `json:"dispute_id"`
	Amount           int             `json:"amount"`
	Status           string          `json:"status"`
	Provider         string          `json:"provider"`
	OutRefundNo      *string         `json:"out_refund_no"`
	ProviderRefundID *string         `json:"provider_refund_id"`
	CompletedAt      *httpx.JSONTime `json:"completed_at"`
}
