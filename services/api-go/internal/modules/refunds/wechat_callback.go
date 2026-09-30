package refunds

import (
	"context"
	"crypto"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/avaargsh/esports-companion/services/api-go/internal/config"
	"github.com/avaargsh/esports-companion/services/api-go/internal/ports"
)

const refundCallbackTimestampSkew = 300 * time.Second

type WeChatCallbackVerifier struct {
	apiV3Key           []byte
	platformCertSerial string
	platformPublicKey  *rsa.PublicKey
	expectedMchID      string
	now                func() time.Time
	maxTimestampSkew   time.Duration
}

func NewWeChatCallbackVerifier(cfg config.Config) (*WeChatCallbackVerifier, error) {
	apiKey := []byte(cfg.WeChatPayAPIV3Key)
	if len(apiKey) != 32 {
		return nil, errorsNew("WECHAT_PAY_API_V3_KEY_MUST_BE_32_BYTES")
	}
	required := []struct {
		name  string
		value string
	}{
		{"WECHAT_PAY_PLATFORM_CERT_SERIAL", cfg.WeChatPayPlatformCertSerial},
		{"WECHAT_PAY_PLATFORM_CERTIFICATE", cfg.WeChatPayPlatformCertificate},
		{"WECHAT_MCH_ID", cfg.WeChatMchID},
	}
	missing := make([]string, 0)
	for _, item := range required {
		if strings.TrimSpace(item.value) == "" {
			missing = append(missing, item.name)
		}
	}
	if len(missing) > 0 {
		return nil, fmt.Errorf(
			"%w:%s",
			ErrWeChatRefundCallbackConfigMissing,
			strings.Join(missing, ","),
		)
	}

	publicKey, err := parseCertificatePublicKey(cfg.WeChatPayPlatformCertificate)
	if err != nil {
		return nil, err
	}
	return &WeChatCallbackVerifier{
		apiV3Key:           apiKey,
		platformCertSerial: normalizeSerial(cfg.WeChatPayPlatformCertSerial),
		platformPublicKey:  publicKey,
		expectedMchID:      cfg.WeChatMchID,
		now:                time.Now,
		maxTimestampSkew:   refundCallbackTimestampSkew,
	}, nil
}

func (v *WeChatCallbackVerifier) VerifyAndDecrypt(
	_ context.Context,
	headers map[string]string,
	body []byte,
) (ports.RefundCallback, error) {
	lowered := make(map[string]string, len(headers))
	for key, value := range headers {
		lowered[strings.ToLower(key)] = value
	}
	timestamp := lowered["wechatpay-timestamp"]
	nonce := lowered["wechatpay-nonce"]
	signature := lowered["wechatpay-signature"]
	serial := lowered["wechatpay-serial"]
	if timestamp == "" || nonce == "" || signature == "" || serial == "" {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackHeadersMissing
	}
	if normalizeSerial(serial) != v.platformCertSerial {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackSerialUnknown
	}

	timestampValue, err := strconv.ParseInt(timestamp, 10, 64)
	if err != nil {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackTimestampInvalid
	}
	if absDuration(v.now().Sub(time.Unix(timestampValue, 0))) > v.maxTimestampSkew {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackTimestampExpired
	}

	decodedSignature, err := base64.StdEncoding.DecodeString(signature)
	if err != nil {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackSignatureInvalid
	}
	message := []byte(timestamp + "\n" + nonce + "\n" + string(body) + "\n")
	digest := sha256.Sum256(message)
	if err := rsa.VerifyPKCS1v15(
		v.platformPublicKey,
		crypto.SHA256,
		digest[:],
		decodedSignature,
	); err != nil {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackSignatureInvalid
	}

	var event map[string]any
	if err := json.Unmarshal(body, &event); err != nil {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackInvalidJSON
	}
	eventType := asString(event["event_type"])
	expectedStatus := ""
	switch eventType {
	case "REFUND.SUCCESS":
		expectedStatus = "SUCCESS"
	case "REFUND.ABNORMAL":
		expectedStatus = "ABNORMAL"
	case "REFUND.CLOSED":
		expectedStatus = "CLOSED"
	default:
		return ports.RefundCallback{}, ErrWeChatRefundCallbackEventUnsupported
	}

	resource, ok := event["resource"].(map[string]any)
	if !ok {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackResourceMissing
	}
	if asString(resource["algorithm"]) != "AEAD_AES_256_GCM" {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackAlgorithmUnsupported
	}
	originalType := asString(resource["original_type"])
	if originalType != "" && originalType != "refund" {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackResourceTypeInvalid
	}
	ciphertextValue := asString(resource["ciphertext"])
	resourceNonce := asString(resource["nonce"])
	if ciphertextValue == "" || resourceNonce == "" {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackResourceInvalid
	}
	ciphertext, err := base64.StdEncoding.DecodeString(ciphertextValue)
	if err != nil {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackResourceInvalid
	}
	associatedData := asString(resource["associated_data"])

	block, err := aes.NewCipher(v.apiV3Key)
	if err != nil {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackDecryptFailed
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackDecryptFailed
	}
	plaintext, err := gcm.Open(
		nil,
		[]byte(resourceNonce),
		ciphertext,
		[]byte(associatedData),
	)
	if err != nil {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackDecryptFailed
	}

	var payload map[string]any
	if err := json.Unmarshal(plaintext, &payload); err != nil {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackDecryptFailed
	}
	if asString(payload["mchid"]) != v.expectedMchID {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackMchIDMismatch
	}
	refundStatus := strings.ToUpper(asString(payload["refund_status"]))
	if refundStatus != expectedStatus {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackStatusMismatch
	}

	amount, ok := payload["amount"].(map[string]any)
	if !ok {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackAmountInvalid
	}
	total, totalOK := jsonNumberToInt64(amount["total"])
	refundAmount, refundOK := jsonNumberToInt64(amount["refund"])
	if !totalOK || !refundOK {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackAmountInvalid
	}

	refundID := asString(payload["refund_id"])
	outRefundNo := asString(payload["out_refund_no"])
	transactionID := asString(payload["transaction_id"])
	orderNo := asString(payload["out_trade_no"])
	if refundID == "" || outRefundNo == "" || transactionID == "" || orderNo == "" {
		return ports.RefundCallback{}, ErrWeChatRefundCallbackIdentifiersMissing
	}

	return ports.RefundCallback{
		Provider:         "WECHAT",
		ProviderRefundID: refundID,
		OutRefundNo:      outRefundNo,
		PaymentTxnID:     transactionID,
		OrderNo:          orderNo,
		RefundStatus:     refundStatus,
		TotalAmount:      total,
		RefundAmount:     refundAmount,
		RawEvent:         event,
		Resource:         payload,
	}, nil
}

func absDuration(value time.Duration) time.Duration {
	if value < 0 {
		return -value
	}
	return value
}

func asString(value any) string {
	result, _ := value.(string)
	return result
}

func jsonNumberToInt64(value any) (int64, bool) {
	switch typed := value.(type) {
	case float64:
		if typed != float64(int64(typed)) {
			return 0, false
		}
		return int64(typed), true
	case int:
		return int64(typed), true
	case int64:
		return typed, true
	default:
		return 0, false
	}
}

type stringError string

func (e stringError) Error() string { return string(e) }

func errorsNew(value string) error { return stringError(value) }
