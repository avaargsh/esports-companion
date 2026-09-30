package refunds

import (
	"errors"

	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/httpx"
)

var (
	ErrRefundNotFound                           = errors.New("REFUND_NOT_FOUND")
	ErrRefundNotSubmittable                     = errors.New("REFUND_NOT_SUBMITTABLE")
	ErrOrderNotRefunding                        = errors.New("ORDER_NOT_REFUNDING")
	ErrSuccessfulPaymentNotFound                = errors.New("SUCCESSFUL_PAYMENT_NOT_FOUND")
	ErrRefundProviderMismatch                   = errors.New("REFUND_PROVIDER_MISMATCH")
	ErrRefundProviderMissing                    = errors.New("REFUND_PROVIDER_NOT_CONFIGURED")
	ErrWeChatRefundCredentialsMissing           = errors.New("WECHAT_REFUND_CREDENTIALS_MISSING")
	ErrWeChatRefundRequiresPayment              = errors.New("WECHAT_REFUND_REQUIRES_SUCCESSFUL_WECHAT_PAYMENT")
	ErrWeChatPaymentTxnMissing                  = errors.New("WECHAT_PAYMENT_TRANSACTION_ID_MISSING")
	ErrRefundOutRefundNoMissing                 = errors.New("REFUND_OUT_REFUND_NO_MISSING")
	ErrWeChatRefundNetwork                      = errors.New("WECHAT_REFUND_NETWORK_ERROR")
	ErrWeChatRefundInvalidJSON                  = errors.New("WECHAT_REFUND_INVALID_JSON")
	ErrWeChatRefundInvalidResponse              = errors.New("WECHAT_REFUND_INVALID_RESPONSE")
	ErrWeChatRefundStatusInvalid                = errors.New("WECHAT_REFUND_STATUS_INVALID")
	ErrWeChatRefundHTTP                         = errors.New("WECHAT_REFUND_HTTP_ERROR")
	ErrWeChatRefundSignatureHeaders             = errors.New("WECHAT_REFUND_RESPONSE_SIGNATURE_HEADERS_MISSING")
	ErrWeChatRefundSerialUnknown                = errors.New("WECHAT_REFUND_RESPONSE_CERT_SERIAL_UNKNOWN")
	ErrWeChatRefundSignatureInvalid             = errors.New("WECHAT_REFUND_RESPONSE_SIGNATURE_INVALID")
	ErrWeChatRefundPrivateKeyInvalid            = errors.New("WECHAT_REFUND_PRIVATE_KEY_INVALID")
	ErrWeChatRefundCertificateInvalid           = errors.New("WECHAT_REFUND_CERTIFICATE_INVALID")
	ErrRefundProviderQueryUnsupported           = errors.New("REFUND_PROVIDER_QUERY_UNSUPPORTED")
	ErrRefundNotReconcilable                    = errors.New("REFUND_NOT_RECONCILABLE")
	ErrRefundProviderIDMismatch                 = errors.New("REFUND_PROVIDER_ID_MISMATCH")
	ErrRefundQueryOutRefundNoMismatch           = errors.New("REFUND_QUERY_OUT_REFUND_NO_MISMATCH")
	ErrRefundQueryOrderNoMismatch               = errors.New("REFUND_QUERY_ORDER_NO_MISMATCH")
	ErrRefundQueryPaymentTxnMismatch            = errors.New("REFUND_QUERY_PAYMENT_TRANSACTION_MISMATCH")
	ErrRefundQueryAmountMismatch                = errors.New("REFUND_QUERY_AMOUNT_MISMATCH")
	ErrRefundOrderNotFound                      = errors.New("REFUND_ORDER_NOT_FOUND")
	ErrRefundOrderNoMismatch                    = errors.New("REFUND_ORDER_NO_MISMATCH")
	ErrRefundTotalAmountMismatch                = errors.New("REFUND_TOTAL_AMOUNT_MISMATCH")
	ErrRefundAmountMismatch                     = errors.New("REFUND_AMOUNT_MISMATCH")
	ErrRefundPaymentTxnMismatch                 = errors.New("REFUND_PAYMENT_TRANSACTION_MISMATCH")
	ErrWeChatRefundQueryNetwork                 = errors.New("WECHAT_REFUND_QUERY_NETWORK_ERROR")
	ErrWeChatRefundQueryInvalidJSON             = errors.New("WECHAT_REFUND_QUERY_INVALID_JSON")
	ErrWeChatRefundQueryInvalidResponse         = errors.New("WECHAT_REFUND_QUERY_INVALID_RESPONSE")
	ErrWeChatRefundQueryHTTP                    = errors.New("WECHAT_REFUND_QUERY_HTTP_ERROR")
	ErrWeChatPayAPIV3KeyInvalid                 = errors.New("WECHAT_PAY_API_V3_KEY_MUST_BE_32_BYTES")
	ErrWeChatRefundCallbackConfigMissing        = errors.New("WECHAT_REFUND_CALLBACK_CONFIG_MISSING")
	ErrWeChatRefundCallbackHeadersMissing       = errors.New("WECHAT_REFUND_CALLBACK_HEADERS_MISSING")
	ErrWeChatRefundCallbackSerialUnknown        = errors.New("WECHAT_REFUND_CALLBACK_CERT_SERIAL_UNKNOWN")
	ErrWeChatRefundCallbackTimestampInvalid     = errors.New("WECHAT_REFUND_CALLBACK_TIMESTAMP_INVALID")
	ErrWeChatRefundCallbackTimestampExpired     = errors.New("WECHAT_REFUND_CALLBACK_TIMESTAMP_EXPIRED")
	ErrWeChatRefundCallbackSignatureInvalid     = errors.New("WECHAT_REFUND_CALLBACK_SIGNATURE_INVALID")
	ErrWeChatRefundCallbackInvalidJSON          = errors.New("WECHAT_REFUND_CALLBACK_INVALID_JSON")
	ErrWeChatRefundCallbackEventUnsupported     = errors.New("WECHAT_REFUND_CALLBACK_EVENT_UNSUPPORTED")
	ErrWeChatRefundCallbackResourceMissing      = errors.New("WECHAT_REFUND_CALLBACK_RESOURCE_MISSING")
	ErrWeChatRefundCallbackAlgorithmUnsupported = errors.New("WECHAT_REFUND_CALLBACK_ALGORITHM_UNSUPPORTED")
	ErrWeChatRefundCallbackResourceTypeInvalid  = errors.New("WECHAT_REFUND_CALLBACK_RESOURCE_TYPE_INVALID")
	ErrWeChatRefundCallbackResourceInvalid      = errors.New("WECHAT_REFUND_CALLBACK_RESOURCE_INVALID")
	ErrWeChatRefundCallbackDecryptFailed        = errors.New("WECHAT_REFUND_CALLBACK_DECRYPT_FAILED")
	ErrWeChatRefundCallbackMchIDMismatch        = errors.New("WECHAT_REFUND_CALLBACK_MCHID_MISMATCH")
	ErrWeChatRefundCallbackStatusMismatch       = errors.New("WECHAT_REFUND_CALLBACK_STATUS_MISMATCH")
	ErrWeChatRefundCallbackAmountInvalid        = errors.New("WECHAT_REFUND_CALLBACK_AMOUNT_INVALID")
	ErrWeChatRefundCallbackIdentifiersMissing   = errors.New("WECHAT_REFUND_CALLBACK_IDENTIFIERS_MISSING")
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

type VerifiedRefundCallback struct {
	Provider         string
	ProviderRefundID string
	OutRefundNo      string
	ProviderTxnID    string
	OutTradeNo       string
	RefundStatus     string
	TotalAmount      int
	RefundAmount     int
	RawEvent         map[string]any
	Resource         map[string]any
}
