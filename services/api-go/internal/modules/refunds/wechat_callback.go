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
)

const refundCallbackTimestampSkew = 300 * time.Second

type WeChatRefundCallbackVerifier struct {
	apiV3Key           []byte
	platformCertSerial string
	platformPublicKey  *rsa.PublicKey
	expectedMchID      string
	now                func() time.Time
	maxTimestampSkew   time.Duration
}

func NewWeChatRefundCallbackVerifier(
	cfg config.Config,
) (*WeChatRefundCallbackVerifier, error) {
	apiKey := []byte(cfg.WeChatPayAPIV3Key)
	if len(apiKey) != 32 {
		return nil, fmt.Errorf(
			"%w:%d",
			ErrWeChatRefundCallbackConfigMissing,
			len(apiKey),
		)
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
	return &WeChatRefundCallbackVerifier{
		apiV3Key:           apiKey,
		platformCertSerial: normalizeSerial(cfg.WeChatPayPlatformCertSerial),
		platformPublicKey:  publicKey,
		expectedMchID:      strings.TrimSpace(cfg.WeChatMchID),
		now:                time.Now,
		maxTimestampSkew:   refundCallbackTimestampSkew,
	}, nil
}

func (v *WeChatRefundCallbackVerifier) VerifyAndDecrypt(
	_ context.Context,
	headers map[string]string,
	body []byte,
) (VerifiedRefundCallback, error) {
	lowered := make(map[string]string, len(headers))
	for key, value := range headers {
		lowered[strings.ToLower(key)] = value
	}

	timestamp := lowered["wechatpay-timestamp"]
	nonce := lowered["wechatpay-nonce"]
	signature := lowered["wechatpay-signature"]
	serial := lowered["wechatpay-serial"]
	if timestamp == "" || nonce == "" || signature == "" || serial == "" {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackHeadersMissing
	}
	if normalizeSerial(serial) != v.platformCertSerial {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackSerialUnknown
	}

	timestampValue, err := strconv.ParseInt(timestamp, 10, 64)
	if err != nil {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackTimestampInvalid
	}
	if absRefundDuration(v.now().Sub(time.Unix(timestampValue, 0))) > v.maxTimestampSkew {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackTimestampExpired
	}

	decodedSignature, err := base64.StdEncoding.DecodeString(signature)
	if err != nil {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackSignatureInvalid
	}
	message := []byte(timestamp + "\n" + nonce + "\n" + string(body) + "\n")
	digest := sha256.Sum256(message)
	if err := rsa.VerifyPKCS1v15(
		v.platformPublicKey,
		crypto.SHA256,
		digest[:],
		decodedSignature,
	); err != nil {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackSignatureInvalid
	}

	var event map[string]any
	if err := json.Unmarshal(body, &event); err != nil {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackInvalidJSON
	}
	eventType := refundString(event["event_type"])
	expectedStatus, ok := map[string]string{
		"REFUND.SUCCESS":  "SUCCESS",
		"REFUND.ABNORMAL": "ABNORMAL",
		"REFUND.CLOSED":   "CLOSED",
	}[eventType]
	if !ok {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackEventUnsupported
	}

	resource, ok := event["resource"].(map[string]any)
	if !ok {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackResourceMissing
	}
	if refundString(resource["algorithm"]) != "AEAD_AES_256_GCM" {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackAlgorithmUnsupported
	}
	if originalType := refundString(resource["original_type"]); originalType != "" && originalType != "refund" {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackResourceTypeInvalid
	}

	ciphertextValue := refundString(resource["ciphertext"])
	resourceNonce := refundString(resource["nonce"])
	if ciphertextValue == "" || resourceNonce == "" {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackResourceInvalid
	}
	ciphertext, err := base64.StdEncoding.DecodeString(ciphertextValue)
	if err != nil {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackResourceInvalid
	}
	associatedData := refundString(resource["associated_data"])

	block, err := aes.NewCipher(v.apiV3Key)
	if err != nil {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackDecryptFailed
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackDecryptFailed
	}
	plaintext, err := gcm.Open(
		nil,
		[]byte(resourceNonce),
		ciphertext,
		[]byte(associatedData),
	)
	if err != nil {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackDecryptFailed
	}

	var payload map[string]any
	if err := json.Unmarshal(plaintext, &payload); err != nil {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackDecryptFailed
	}
	if refundString(payload["mchid"]) != v.expectedMchID {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackMchIDMismatch
	}
	refundStatus := strings.ToUpper(refundString(payload["refund_status"]))
	if refundStatus != expectedStatus {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackStatusMismatch
	}

	amount, ok := payload["amount"].(map[string]any)
	if !ok {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackAmountInvalid
	}
	total, ok := refundJSONInt(amount["total"])
	if !ok {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackAmountInvalid
	}
	refundAmount, ok := refundJSONInt(amount["refund"])
	if !ok {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackAmountInvalid
	}

	providerRefundID := refundString(payload["refund_id"])
	outRefundNo := refundString(payload["out_refund_no"])
	providerTxnID := refundString(payload["transaction_id"])
	outTradeNo := refundString(payload["out_trade_no"])
	if providerRefundID == "" || outRefundNo == "" || providerTxnID == "" || outTradeNo == "" {
		return VerifiedRefundCallback{}, ErrWeChatRefundCallbackIdentifiersMissing
	}

	return VerifiedRefundCallback{
		Provider:         "WECHAT",
		ProviderRefundID: providerRefundID,
		OutRefundNo:      outRefundNo,
		ProviderTxnID:    providerTxnID,
		OutTradeNo:       outTradeNo,
		RefundStatus:     refundStatus,
		TotalAmount:      total,
		RefundAmount:     refundAmount,
		RawEvent:         event,
		Resource:         payload,
	}, nil
}

func absRefundDuration(value time.Duration) time.Duration {
	if value < 0 {
		return -value
	}
	return value
}

func refundString(value any) string {
	result, _ := value.(string)
	return result
}

func refundJSONInt(value any) (int, bool) {
	switch typed := value.(type) {
	case float64:
		if typed != float64(int(typed)) {
			return 0, false
		}
		return int(typed), true
	case int:
		return typed, true
	case int64:
		return int(typed), true
	case json.Number:
		value, err := typed.Int64()
		if err != nil {
			return 0, false
		}
		return int(value), true
	default:
		return 0, false
	}
}
