package payments

import (
	"context"
	"crypto"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
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

func TestWeChatCallbackVerifierVerifiesAndDecrypts(t *testing.T) {
	verifier, privateKey, headers, body := signedCallbackFixture(t)
	result, err := verifier.VerifyAndDecrypt(context.Background(), headers, body)
	if err != nil {
		t.Fatal(err)
	}
	if result.Provider != "WECHAT" ||
		result.ProviderTxnID != "wx-txn-1" ||
		result.OrderNo != "ORD_CALLBACK" ||
		result.AmountMinor != 3000 ||
		result.Currency != "CNY" ||
		result.PayerSubject != "openid-1" {
		t.Fatalf("callback = %#v", result)
	}

	tampered := append([]byte(nil), body...)
	for i := range tampered {
		if tampered[i] == '1' {
			tampered[i] = 'X'
			break
		}
	}
	_, err = verifier.VerifyAndDecrypt(context.Background(), headers, tampered)
	if err != ErrWeChatCallbackSignatureInvalid {
		t.Fatalf("tampered callback error = %v", err)
	}

	expiredHeaders := cloneHeaders(headers)
	expiredHeaders["Wechatpay-Timestamp"] = fmt.Sprintf("%d", verifier.now().Add(-10*time.Minute).Unix())
	expiredHeaders["Wechatpay-Signature"] = signCallback(
		t,
		privateKey,
		expiredHeaders["Wechatpay-Timestamp"],
		expiredHeaders["Wechatpay-Nonce"],
		body,
	)
	_, err = verifier.VerifyAndDecrypt(context.Background(), expiredHeaders, body)
	if err != ErrWeChatCallbackTimestampExpired {
		t.Fatalf("expired callback error = %v", err)
	}
}

func signedCallbackFixture(
	t *testing.T,
) (*WeChatCallbackVerifier, *rsa.PrivateKey, map[string]string, []byte) {
	t.Helper()
	privateKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Unix(1_790_000_000, 0)
	template := &x509.Certificate{
		SerialNumber: big.NewInt(0x1234ABCD),
		Subject:      pkix.Name{CommonName: "wechat-platform-test"},
		Issuer:       pkix.Name{CommonName: "wechat-platform-test"},
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
	verifier, err := NewWeChatCallbackVerifier(config.Config{
		WeChatAppID:                  "wx-app",
		WeChatMchID:                  "mch-1",
		WeChatPayAPIV3Key:            apiKey,
		WeChatPayPlatformCertSerial:  "1234ABCD",
		WeChatPayPlatformCertificate: certPEM,
	})
	if err != nil {
		t.Fatal(err)
	}
	verifier.now = func() time.Time { return now }

	resource := map[string]any{
		"mchid":          "mch-1",
		"appid":          "wx-app",
		"out_trade_no":   "ORD_CALLBACK",
		"transaction_id": "wx-txn-1",
		"trade_state":    "SUCCESS",
		"payer":          map[string]any{"openid": "openid-1"},
		"amount":         map[string]any{"total": 3000, "currency": "CNY"},
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
	resourceNonce := []byte("callback-nce")
	associated := []byte("transaction")
	encrypted := gcm.Seal(nil, resourceNonce, plaintext, associated)

	event := map[string]any{
		"id":            "event-1",
		"event_type":    "TRANSACTION.SUCCESS",
		"resource_type": "encrypt-resource",
		"resource": map[string]any{
			"algorithm":       "AEAD_AES_256_GCM",
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
	headerNonce := "header-nonce"
	headers := map[string]string{
		"Wechatpay-Timestamp": timestamp,
		"Wechatpay-Nonce":     headerNonce,
		"Wechatpay-Serial":    "1234ABCD",
	}
	headers["Wechatpay-Signature"] = signCallback(
		t,
		privateKey,
		timestamp,
		headerNonce,
		body,
	)
	return verifier, privateKey, headers, body
}

func signCallback(
	t *testing.T,
	privateKey *rsa.PrivateKey,
	timestamp string,
	nonce string,
	body []byte,
) string {
	t.Helper()
	message := []byte(timestamp + "\n" + nonce + "\n" + string(body) + "\n")
	digest := sha256.Sum256(message)
	signature, err := rsa.SignPKCS1v15(
		rand.Reader,
		privateKey,
		crypto.SHA256,
		digest[:],
	)
	if err != nil {
		t.Fatal(err)
	}
	return base64.StdEncoding.EncodeToString(signature)
}

func cloneHeaders(source map[string]string) map[string]string {
	target := make(map[string]string, len(source))
	for key, value := range source {
		target[key] = value
	}
	return target
}
