package payments

import (
	"context"
	"crypto"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/avaargsh/esports-companion/services/api-go/internal/config"
	"github.com/avaargsh/esports-companion/services/api-go/internal/ports"
)

const callbackTimestampSkew = 300 * time.Second

type WeChatCallbackVerifier struct {
	apiV3Key          []byte
	platformCertSerial string
	platformPublicKey *rsa.PublicKey
	expectedAppID     string
	expectedMchID     string
	now               func() time.Time
	maxTimestampSkew  time.Duration
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
		{"WECHAT_APP_ID", cfg.WeChatAppID},
		{"WECHAT_MCH_ID", cfg.WeChatMchID},
	}
	missing := make([]string, 0)
	for _, item := range required {
		if strings.TrimSpace(item.value) == "" {
			missing = append(missing, item.name)
		}
	}
	if len(missing) > 0 {
		return nil, fmt.Errorf("%w:%s", ErrWeChatCallbackConfigMissing, strings.Join(missing, ","))
	}

	publicKey, err := parseCertificatePublicKey(cfg.WeChatPayPlatformCertificate)
	if err != nil {
		return nil, err
	}
	return &WeChatCallbackVerifier{
		apiV3Key:           apiKey,
		platformCertSerial: normalizeSerial(cfg.WeChatPayPlatformCertSerial),
		platformPublicKey:  publicKey,
		expectedAppID:      cfg.WeChatAppID,
		expectedMchID:      cfg.WeChatMchID,
		now:                time.Now,
		maxTimestampSkew:   callbackTimestampSkew,
	}, nil
}

func (v *WeChatCallbackVerifier) VerifyAndDecrypt(
	_ context.Context,
	headers map[string]string,
	body []byte,
) (ports.PaymentCallback, error) {
	lowered := make(map[string]string, len(headers))
	for key, value := range headers {
		lowered[strings.ToLower(key)] = value
	}

	timestamp := lowered["wechatpay-timestamp"]
	nonce := lowered["wechatpay-nonce"]
	signature := lowered["wechatpay-signature"]
	serial := lowered["wechatpay-serial"]
	if timestamp == "" || nonce == "" || signature == "" || serial == "" {
		return ports.PaymentCallback{}, ErrWeChatCallbackHeadersMissing
	}
	if normalizeSerial(serial) != v.platformCertSerial {
		return ports.PaymentCallback{}, ErrWeChatCallbackSerialUnknown
	}

	timestampValue, err := strconv.ParseInt(timestamp, 10, 64)
	if err != nil {
		return ports.PaymentCallback{}, ErrWeChatCallbackTimestampInvalid
	}
	if absDuration(v.now().Sub(time.Unix(timestampValue, 0))) > v.maxTimestampSkew {
		return ports.PaymentCallback{}, ErrWeChatCallbackTimestampExpired
	}

	decodedSignature, err := base64.StdEncoding.DecodeString(signature)
	if err != nil {
		return ports.PaymentCallback{}, ErrWeChatCallbackSignatureInvalid
	}
	message := []byte(timestamp + "\n" + nonce + "\n" + string(body) + "\n")
	digest := sha256.Sum256(message)
	if err := rsa.VerifyPKCS1v15(
		v.platformPublicKey,
		crypto.SHA256,
		digest[:],
		decodedSignature,
	); err != nil {
		return ports.PaymentCallback{}, ErrWeChatCallbackSignatureInvalid
	}

	var event map[string]any
	if err := json.Unmarshal(body, &event); err != nil {
		return ports.PaymentCallback{}, ErrWeChatCallbackInvalidJSON
	}
	resource, ok := event["resource"].(map[string]any)
	if !ok {
		return ports.PaymentCallback{}, ErrWeChatCallbackResourceMissing
	}
	if asString(resource["algorithm"]) != "AEAD_AES_256_GCM" {
		return ports.PaymentCallback{}, ErrWeChatCallbackAlgorithmUnsupported
	}

	ciphertextValue := asString(resource["ciphertext"])
	resourceNonce := asString(resource["nonce"])
	if ciphertextValue == "" || resourceNonce == "" {
		return ports.PaymentCallback{}, ErrWeChatCallbackResourceInvalid
	}
	ciphertext, err := base64.StdEncoding.DecodeString(ciphertextValue)
	if err != nil {
		return ports.PaymentCallback{}, ErrWeChatCallbackResourceInvalid
	}
	associatedData := asString(resource["associated_data"])

	block, err := aes.NewCipher(v.apiV3Key)
	if err != nil {
		return ports.PaymentCallback{}, ErrWeChatCallbackDecryptFailed
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return ports.PaymentCallback{}, ErrWeChatCallbackDecryptFailed
	}
	plaintext, err := gcm.Open(
		nil,
		[]byte(resourceNonce),
		ciphertext,
		[]byte(associatedData),
	)
	if err != nil {
		return ports.PaymentCallback{}, ErrWeChatCallbackDecryptFailed
	}

	var payment map[string]any
	if err := json.Unmarshal(plaintext, &payment); err != nil {
		return ports.PaymentCallback{}, ErrWeChatCallbackDecryptFailed
	}
	if asString(event["event_type"]) != "TRANSACTION.SUCCESS" {
		return ports.PaymentCallback{}, ErrWeChatCallbackEventUnsupported
	}
	if asString(payment["trade_state"]) != "SUCCESS" {
		return ports.PaymentCallback{}, ErrWeChatCallbackTradeNotSuccess
	}
	if asString(payment["appid"]) != v.expectedAppID {
		return ports.PaymentCallback{}, ErrWeChatCallbackAppIDMismatch
	}
	if asString(payment["mchid"]) != v.expectedMchID {
		return ports.PaymentCallback{}, ErrWeChatCallbackMchIDMismatch
	}

	amount, ok := payment["amount"].(map[string]any)
	if !ok {
		return ports.PaymentCallback{}, ErrWeChatCallbackAmountInvalid
	}
	total, ok := jsonNumberToInt64(amount["total"])
	if !ok {
		return ports.PaymentCallback{}, ErrWeChatCallbackAmountInvalid
	}
	transactionID := asString(payment["transaction_id"])
	orderNo := asString(payment["out_trade_no"])
	if transactionID == "" || orderNo == "" {
		return ports.PaymentCallback{}, ErrWeChatCallbackIdentifiersMissing
	}

	payerSubject := ""
	if payer, ok := payment["payer"].(map[string]any); ok {
		payerSubject = asString(payer["openid"])
	}
	currency := asString(amount["currency"])
	if currency == "" {
		currency = "CNY"
	}

	return ports.PaymentCallback{
		Provider:      "WECHAT",
		ProviderTxnID: transactionID,
		OrderNo:       orderNo,
		PayerSubject:  payerSubject,
		Currency:      currency,
		AmountMinor:   total,
		RawEvent:      event,
		Resource:      payment,
	}, nil
}

func parseCertificatePublicKey(value string) (*rsa.PublicKey, error) {
	material := strings.ReplaceAll(strings.TrimSpace(value), "\\n", "\n")
	block, _ := pem.Decode([]byte(material))
	if block == nil {
		return nil, errorsNew("WECHAT_CALLBACK_CERTIFICATE_INVALID")
	}
	certificate, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		return nil, errorsNew("WECHAT_CALLBACK_CERTIFICATE_INVALID")
	}
	publicKey, ok := certificate.PublicKey.(*rsa.PublicKey)
	if !ok {
		return nil, errorsNew("WECHAT_CALLBACK_CERTIFICATE_INVALID")
	}
	return publicKey, nil
}

func normalizeSerial(value string) string {
	value = strings.ToUpper(strings.TrimSpace(value))
	value = strings.TrimLeft(value, "0")
	if value == "" {
		return "0"
	}
	return value
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
