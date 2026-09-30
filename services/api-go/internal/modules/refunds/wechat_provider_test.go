package refunds

import (
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"io"
	"math/big"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/avaargsh/esports-companion/services/api-go/internal/ports"
)

func TestWeChatProviderCreateRefundSignsRequestAndVerifiesResponse(t *testing.T) {
	merchantKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	merchantDER, err := x509.MarshalPKCS8PrivateKey(merchantKey)
	if err != nil {
		t.Fatal(err)
	}
	merchantPEM := string(pem.EncodeToMemory(&pem.Block{
		Type:  "PRIVATE KEY",
		Bytes: merchantDER,
	}))

	platformKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Unix(1_790_000_000, 0)
	template := &x509.Certificate{
		SerialNumber: big.NewInt(0x77AABBCC),
		Subject:      pkix.Name{CommonName: "wechat-refund-platform"},
		Issuer:       pkix.Name{CommonName: "wechat-refund-platform"},
		NotBefore:    now.Add(-time.Hour),
		NotAfter:     now.Add(time.Hour),
		KeyUsage:     x509.KeyUsageDigitalSignature,
	}
	certDER, err := x509.CreateCertificate(
		rand.Reader,
		template,
		template,
		&platformKey.PublicKey,
		platformKey,
	)
	if err != nil {
		t.Fatal(err)
	}
	certPEM := string(pem.EncodeToMemory(&pem.Block{
		Type:  "CERTIFICATE",
		Bytes: certDER,
	}))

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != weChatRefundPath {
			http.Error(w, "bad request", http.StatusBadRequest)
			return
		}
		body, readErr := io.ReadAll(r.Body)
		if readErr != nil {
			t.Errorf("read request: %v", readErr)
			http.Error(w, "read request", http.StatusBadRequest)
			return
		}
		var payload map[string]any
		if decodeErr := json.Unmarshal(body, &payload); decodeErr != nil {
			t.Errorf("decode request: %v", decodeErr)
			http.Error(w, "decode request", http.StatusBadRequest)
			return
		}
		if payload["transaction_id"] != "wx-payment-1" ||
			payload["out_refund_no"] != "RFD_TEST" ||
			payload["notify_url"] != "https://api.example.com/refunds/wechat/callback" {
			t.Errorf("request payload = %#v", payload)
		}
		amount, ok := payload["amount"].(map[string]any)
		if !ok ||
			amount["refund"] != float64(1200) ||
			amount["total"] != float64(3000) ||
			amount["currency"] != "CNY" {
			t.Errorf("amount payload = %#v", payload["amount"])
		}

		auth := r.Header.Get("Authorization")
		signature := refundAuthField(auth, "signature")
		if refundAuthField(auth, "mchid") != "mch-1" ||
			refundAuthField(auth, "serial_no") != "merchant-serial" ||
			refundAuthField(auth, "nonce_str") != "merchant-nonce" ||
			refundAuthField(auth, "timestamp") != fmt.Sprintf("%d", now.Unix()) {
			t.Errorf("authorization = %s", auth)
		}
		requestMessage := []byte(
			"POST\n" + weChatRefundPath + "\n" +
				fmt.Sprintf("%d", now.Unix()) + "\n" +
				"merchant-nonce\n" + string(body) + "\n",
		)
		verifyRefundSignature(t, &merchantKey.PublicKey, requestMessage, signature)

		responseBody := []byte(
			"{\"refund_id\":\"wx-refund-1\",\"out_refund_no\":\"RFD_TEST\",\"status\":\"PROCESSING\"}",
		)
		responseTimestamp := fmt.Sprintf("%d", now.Unix())
		responseNonce := "platform-nonce"
		responseMessage := []byte(
			responseTimestamp + "\n" +
				responseNonce + "\n" +
				string(responseBody) + "\n",
		)
		responseSignature := signRefundMessage(t, platformKey, responseMessage)
		w.Header().Set("Wechatpay-Timestamp", responseTimestamp)
		w.Header().Set("Wechatpay-Nonce", responseNonce)
		w.Header().Set("Wechatpay-Serial", "77AABBCC")
		w.Header().Set("Wechatpay-Signature", responseSignature)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write(responseBody)
	}))
	defer server.Close()

	provider, err := NewWeChatProvider(WeChatProviderConfig{
		MchID:               "mch-1",
		CertSerial:          "merchant-serial",
		PrivateKey:          merchantPEM,
		NotifyURL:           "https://api.example.com/refunds/wechat/callback",
		APIBaseURL:          server.URL,
		Timeout:             time.Second,
		PlatformCertSerial:  "77AABBCC",
		PlatformCertificate: certPEM,
	})
	if err != nil {
		t.Fatal(err)
	}
	provider.now = func() time.Time { return now }
	provider.nonce = func() (string, error) { return "merchant-nonce", nil }

	intent, err := provider.CreateRefund(context.Background(), ports.RefundRequest{
		RefundID:       "refund-1",
		OutRefundNo:    "RFD_TEST",
		OrderID:        "order-1",
		OrderNo:        "ORD_1",
		PaymentTxnID:   "wx-payment-1",
		RefundAmount:   1200,
		TotalAmount:    3000,
		Currency:       "CNY",
		IdempotencyKey: "RFD_TEST",
		Reason:         "Dispute refund",
	})
	if err != nil {
		t.Fatal(err)
	}
	if intent.Provider != "WECHAT" ||
		intent.ProviderRefundID != "wx-refund-1" ||
		intent.Status != "PROCESSING" {
		t.Fatalf("intent = %#v", intent)
	}
	if intent.RawPayload["out_refund_no"] != "RFD_TEST" {
		t.Fatalf("raw payload = %#v", intent.RawPayload)
	}
}

func refundAuthField(header string, name string) string {
	header = strings.TrimPrefix(header, "WECHATPAY2-SHA256-RSA2048 ")
	for _, field := range strings.Split(header, ",") {
		parts := strings.SplitN(strings.TrimSpace(field), "=", 2)
		if len(parts) == 2 && parts[0] == name {
			return strings.Trim(parts[1], "\"")
		}
	}
	return ""
}

func signRefundMessage(
	t *testing.T,
	privateKey *rsa.PrivateKey,
	message []byte,
) string {
	t.Helper()
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

func verifyRefundSignature(
	t *testing.T,
	publicKey *rsa.PublicKey,
	message []byte,
	encodedSignature string,
) {
	t.Helper()
	signature, err := base64.StdEncoding.DecodeString(encodedSignature)
	if err != nil {
		t.Fatal(err)
	}
	digest := sha256.Sum256(message)
	if err := rsa.VerifyPKCS1v15(
		publicKey,
		crypto.SHA256,
		digest[:],
		signature,
	); err != nil {
		t.Fatalf("verify signature: %v", err)
	}
}
