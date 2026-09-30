package refunds

import (
	"context"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"math/big"
	"testing"
	"time"

	"github.com/avaargsh/esports-companion/services/api-go/internal/config"
)

func TestWeChatRefundCallbackVerifierVerifiesAndDecrypts(t *testing.T) {
	verifier, privateKey, headers, body := signedRefundCallbackFixture(t)

	callback, err := verifier.VerifyAndDecrypt(
		context.Background(),
		headers,
		body,
	)
	if err != nil {
		t.Fatal(err)
	}
	if callback.Provider != "WECHAT" ||
		callback.ProviderRefundID != "wx-refund-callback-1" ||
		callback.OutRefundNo != "RFD_CALLBACK" ||
		callback.ProviderTxnID != "wx-payment-callback-1" ||
		callback.OutTradeNo != "ORD_REFUND_CALLBACK" ||
		callback.RefundStatus != "SUCCESS" ||
		callback.TotalAmount != 3000 ||
		callback.RefundAmount != 3000 {
		t.Fatalf("callback = %#v", callback)
	}

	tampered := append([]byte(nil), body...)
	for i := range tampered {
		if tampered[i] == '1' {
			tampered[i] = 'X'
			break
		}
	}
	_, err = verifier.VerifyAndDecrypt(
		context.Background(),
		headers,
		tampered,
	)
	if err != ErrWeChatRefundCallbackSignatureInvalid {
		t.Fatalf("tampered callback error = %v", err)
	}

	expiredHeaders := cloneRefundHeaders(headers)
	expiredHeaders["Wechatpay-Timestamp"] = fmt.Sprintf(
		"%d",
		verifier.now().Add(-10*time.Minute).Unix(),
	)
	expiredHeaders["Wechatpay-Signature"] = signRefundMessage(
		t,
		privateKey,
		[]byte(
			expiredHeaders["Wechatpay-Timestamp"]+"\n"+
				expiredHeaders["Wechatpay-Nonce"]+"\n"+
				string(body)+"\n",
		),
	)
	_, err = verifier.VerifyAndDecrypt(
		context.Background(),
		expiredHeaders,
		body,
	)
	if err != ErrWeChatRefundCallbackTimestampExpired {
		t.Fatalf("expired callback error = %v", err)
	}
}

func signedRefundCallbackFixture(
	t *testing.T,
) (*WeChatRefundCallbackVerifier, *rsa.PrivateKey, map[string]string, []byte) {
	t.Helper()
	privateKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Unix(1_790_000_200, 0)
	template := &x509.Certificate{
		SerialNumber: big.NewInt(0xAABBCCDD),
		Subject:      pkix.Name{CommonName: "wechat-refund-callback-platform"},
		Issuer:       pkix.Name{CommonName: "wechat-refund-callback-platform"},
		NotBefore:    now.Add(-time.Hour),
		NotAfter:     now.Add(time.Hour),
		KeyUsage:     x509.KeyUsageDigitalSignature,
	}
	der, err := x509.CreateCertificate(
		rand.Reader,
		template,
		template,
		&privateKey.PublicKey,
		privateKey,
	)
	if err != nil {
		t.Fatal(err)
	}
	certPEM := string(pem.EncodeToMemory(&pem.Block{
		Type:  "CERTIFICATE",
		Bytes: der,
	}))

	apiKey := "0123456789abcdef0123456789abcdef"
	verifier, err := NewWeChatRefundCallbackVerifier(config.Config{
		WeChatMchID:                  "mch-refund",
		WeChatPayAPIV3Key:            apiKey,
		WeChatPayPlatformCertSerial:  "AABBCCDD",
		WeChatPayPlatformCertificate: certPEM,
	})
	if err != nil {
		t.Fatal(err)
	}
	verifier.now = func() time.Time { return now }

	resource := map[string]any{
		"mchid":          "mch-refund",
		"refund_id":      "wx-refund-callback-1",
		"out_refund_no":  "RFD_CALLBACK",
		"transaction_id": "wx-payment-callback-1",
		"out_trade_no":   "ORD_REFUND_CALLBACK",
		"refund_status":  "SUCCESS",
		"amount": map[string]any{
			"total":  3000,
			"refund": 3000,
		},
	}
	plaintext, err := json.Marshal(resource)
	if err != nil {
		t.Fatal(err)
	}
	block, err := aes.NewCipher([]byte(apiKey))
	if err != nil {
		t.Fatal(err)
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		t.Fatal(err)
	}
	resourceNonce := []byte("refund-nonce")
	associated := []byte("refund")
	encrypted := gcm.Seal(nil, resourceNonce, plaintext, associated)

	event := map[string]any{
		"id":         "refund-event-1",
		"event_type": "REFUND.SUCCESS",
		"resource": map[string]any{
			"algorithm":       "AEAD_AES_256_GCM",
			"original_type":   "refund",
			"ciphertext":      base64.StdEncoding.EncodeToString(encrypted),
			"nonce":           string(resourceNonce),
			"associated_data": string(associated),
		},
	}
	body, err := json.Marshal(event)
	if err != nil {
		t.Fatal(err)
	}
	timestamp := fmt.Sprintf("%d", now.Unix())
	headerNonce := "refund-header-nonce"
	headers := map[string]string{
		"Wechatpay-Timestamp": timestamp,
		"Wechatpay-Nonce":     headerNonce,
		"Wechatpay-Serial":    "AABBCCDD",
	}
	headers["Wechatpay-Signature"] = signRefundMessage(
		t,
		privateKey,
		[]byte(timestamp+"\n"+headerNonce+"\n"+string(body)+"\n"),
	)
	return verifier, privateKey, headers, body
}

func cloneRefundHeaders(source map[string]string) map[string]string {
	target := make(map[string]string, len(source))
	for key, value := range source {
		target[key] = value
	}
	return target
}
