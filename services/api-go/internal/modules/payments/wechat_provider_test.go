package payments

import (
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/avaargsh/esports-companion/services/api-go/internal/ports"
)

func TestWeChatProviderCreatePaymentSignsProviderAndClientRequests(t *testing.T) {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	keyDER, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		t.Fatal(err)
	}
	keyPEM := string(pem.EncodeToMemory(&pem.Block{
		Type:  "PRIVATE KEY",
		Bytes: keyDER,
	}))

	fixedTime := time.Unix(1_790_000_000, 0)
	var requestBody []byte
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Fatalf("method = %s", r.Method)
		}
		if r.URL.Path != weChatJSAPIPath {
			t.Fatalf("path = %s", r.URL.Path)
		}
		requestBody, err = io.ReadAll(r.Body)
		if err != nil {
			t.Fatal(err)
		}

		var payload map[string]any
		if err := json.Unmarshal(requestBody, &payload); err != nil {
			t.Fatal(err)
		}
		if payload["appid"] != "wx-app" || payload["mchid"] != "mch-1" {
			t.Fatalf("merchant identity payload = %#v", payload)
		}
		if payload["out_trade_no"] != "ORD_TEST_1" {
			t.Fatalf("out_trade_no = %#v", payload["out_trade_no"])
		}
		amount, ok := payload["amount"].(map[string]any)
		if !ok || amount["total"] != float64(3000) || amount["currency"] != "CNY" {
			t.Fatalf("amount = %#v", payload["amount"])
		}
		payer, ok := payload["payer"].(map[string]any)
		if !ok || payer["openid"] != "openid-1" {
			t.Fatalf("payer = %#v", payload["payer"])
		}

		auth := r.Header.Get("Authorization")
		signature := authField(auth, "signature")
		if authField(auth, "mchid") != "mch-1" ||
			authField(auth, "serial_no") != "serial-1" ||
			authField(auth, "nonce_str") != "provider-nonce" ||
			authField(auth, "timestamp") != fmt.Sprintf("%d", fixedTime.Unix()) {
			t.Fatalf("authorization = %s", auth)
		}
		message := []byte(
			"POST\n" + weChatJSAPIPath + "\n" +
				fmt.Sprintf("%d", fixedTime.Unix()) + "\n" +
				"provider-nonce\n" + string(requestBody) + "\n",
		)
		verifyRSASignature(t, &key.PublicKey, message, signature)

		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte("{\"prepay_id\":\"wx-prepay-123\"}"))
	}))
	defer server.Close()

	provider, err := NewWeChatProvider(WeChatProviderConfig{
		AppID:      "wx-app",
		MchID:      "mch-1",
		CertSerial: "serial-1",
		PrivateKey: keyPEM,
		NotifyURL:  "https://api.example.com/api/v1/payments/wechat/callback",
		APIBaseURL: server.URL,
		Timeout:    time.Second,
	})
	if err != nil {
		t.Fatal(err)
	}
	provider.now = func() time.Time { return fixedTime }
	nonces := []string{"provider-nonce", "client-nonce"}
	provider.nonce = func() (string, error) {
		value := nonces[0]
		nonces = nonces[1:]
		return value, nil
	}

	intent, err := provider.CreatePayment(context.Background(), ports.PaymentRequest{
		OrderID:        "order-id",
		OrderNo:        "ORD_TEST_1",
		Description:    "Esports Companion ORD_TEST_1",
		AmountMinor:    3000,
		Currency:       "CNY",
		IdempotencyKey: "idem-1",
		PayerSubject:   "openid-1",
	})
	if err != nil {
		t.Fatal(err)
	}
	if intent.Provider != "WECHAT" || intent.Status != "PENDING" {
		t.Fatalf("intent = %#v", intent)
	}
	if intent.ProviderTxnID != "wx-prepay-123" {
		t.Fatalf("provider txn id = %q", intent.ProviderTxnID)
	}
	if intent.ClientPayload["timeStamp"] != fmt.Sprintf("%d", fixedTime.Unix()) ||
		intent.ClientPayload["nonceStr"] != "client-nonce" ||
		intent.ClientPayload["package"] != "prepay_id=wx-prepay-123" ||
		intent.ClientPayload["signType"] != "RSA" {
		t.Fatalf("client payload = %#v", intent.ClientPayload)
	}
	clientMessage := []byte(
		"wx-app\n" +
			fmt.Sprintf("%d", fixedTime.Unix()) + "\n" +
			"client-nonce\n" +
			"prepay_id=wx-prepay-123\n",
	)
	verifyRSASignature(
		t,
		&key.PublicKey,
		clientMessage,
		intent.ClientPayload["paySign"],
	)
	if intent.RawPayload["outTradeNo"] != "ORD_TEST_1" ||
		intent.RawPayload["prepayId"] != "wx-prepay-123" {
		t.Fatalf("raw payload = %#v", intent.RawPayload)
	}
}

func TestWeChatProviderRequiresPayerOpenID(t *testing.T) {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	keyDER, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		t.Fatal(err)
	}
	provider, err := NewWeChatProvider(WeChatProviderConfig{
		AppID:      "wx-app",
		MchID:      "mch-1",
		CertSerial: "serial-1",
		PrivateKey: string(pem.EncodeToMemory(&pem.Block{
			Type:  "PRIVATE KEY",
			Bytes: keyDER,
		})),
		NotifyURL: "https://api.example.com/callback",
	})
	if err != nil {
		t.Fatal(err)
	}
	_, err = provider.CreatePayment(context.Background(), ports.PaymentRequest{
		OrderNo:     "ORD_TEST_2",
		AmountMinor: 3000,
		Currency:    "CNY",
	})
	if err != ErrWeChatPayerOpenIDRequired {
		t.Fatalf("error = %v", err)
	}
}

func authField(header string, name string) string {
	prefix := "WECHATPAY2-SHA256-RSA2048 "
	header = strings.TrimPrefix(header, prefix)
	for _, field := range strings.Split(header, ",") {
		parts := strings.SplitN(strings.TrimSpace(field), "=", 2)
		if len(parts) != 2 || parts[0] != name {
			continue
		}
		return strings.Trim(parts[1], "\"")
	}
	return ""
}

func verifyRSASignature(
	t *testing.T,
	publicKey *rsa.PublicKey,
	message []byte,
	encodedSignature string,
) {
	t.Helper()
	signature, err := base64.StdEncoding.DecodeString(encodedSignature)
	if err != nil {
		t.Fatalf("decode signature: %v", err)
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
