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
	"strings"
	"time"

	"github.com/avaargsh/esports-companion/services/api-go/internal/config"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/idgen"
	"github.com/avaargsh/esports-companion/services/api-go/internal/ports"
)

const weChatJSAPIPath = "/v3/pay/transactions/jsapi"

type httpDoer interface {
	Do(*http.Request) (*http.Response, error)
}

type WeChatProviderConfig struct {
	AppID      string
	MchID      string
	CertSerial string
	PrivateKey string
	NotifyURL  string
	APIBaseURL string
	Timeout    time.Duration
}

type WeChatProvider struct {
	cfg        WeChatProviderConfig
	privateKey *rsa.PrivateKey
	client     httpDoer
	now        func() time.Time
	nonce      func() (string, error)
}

func ProviderFromConfig(cfg config.Config) (ports.PaymentProvider, error) {
	switch strings.ToLower(strings.TrimSpace(cfg.PaymentProvider)) {
	case "mock":
		return MockProvider{}, nil
	case "wechat":
		return NewWeChatProvider(WeChatProviderConfig{
			AppID:      cfg.WeChatAppID,
			MchID:      cfg.WeChatMchID,
			CertSerial: cfg.WeChatMchCertSerial,
			PrivateKey: cfg.WeChatMchPrivateKey,
			NotifyURL:  cfg.WeChatNotifyURL,
			APIBaseURL: cfg.WeChatPayAPIBaseURL,
			Timeout:    cfg.WeChatPayTimeout,
		})
	default:
		return nil, fmt.Errorf("%w:%s", ErrPaymentProviderMissing, cfg.PaymentProvider)
	}
}

func NewWeChatProvider(cfg WeChatProviderConfig) (*WeChatProvider, error) {
	required := []struct {
		name  string
		value string
	}{
		{"WECHAT_APP_ID", cfg.AppID},
		{"WECHAT_MCH_ID", cfg.MchID},
		{"WECHAT_MCH_CERT_SERIAL", cfg.CertSerial},
		{"WECHAT_MCH_PRIVATE_KEY", cfg.PrivateKey},
		{"WECHAT_NOTIFY_URL", cfg.NotifyURL},
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
			ErrWeChatPaymentCredentialsMissing,
			strings.Join(missing, ","),
		)
	}
	privateKey, err := parseRSAPrivateKey(cfg.PrivateKey)
	if err != nil {
		return nil, err
	}
	baseURL := strings.TrimRight(strings.TrimSpace(cfg.APIBaseURL), "/")
	if baseURL == "" {
		baseURL = "https://api.mch.weixin.qq.com"
	}
	timeout := cfg.Timeout
	if timeout <= 0 {
		timeout = 8 * time.Second
	}
	return &WeChatProvider{
		cfg: WeChatProviderConfig{
			AppID:      strings.TrimSpace(cfg.AppID),
			MchID:      strings.TrimSpace(cfg.MchID),
			CertSerial: strings.TrimSpace(cfg.CertSerial),
			PrivateKey: cfg.PrivateKey,
			NotifyURL:  strings.TrimSpace(cfg.NotifyURL),
			APIBaseURL: baseURL,
			Timeout:    timeout,
		},
		privateKey: privateKey,
		client:     &http.Client{Timeout: timeout},
		now:        time.Now,
		nonce:      randomNonce,
	}, nil
}

func (p *WeChatProvider) Name() string {
	return "WECHAT"
}

func (p *WeChatProvider) CreatePayment(
	ctx context.Context,
	request ports.PaymentRequest,
) (ports.PaymentIntent, error) {
	if strings.TrimSpace(request.PayerSubject) == "" {
		return ports.PaymentIntent{}, ErrWeChatPayerOpenIDRequired
	}
	currency := strings.ToUpper(strings.TrimSpace(request.Currency))
	if currency == "" {
		currency = "CNY"
	}
	description := strings.TrimSpace(request.Description)
	if description == "" {
		description = "Esports Companion " + request.OrderNo
	}

	bodyPayload := struct {
		AppID       string `json:"appid"`
		MchID       string `json:"mchid"`
		Description string `json:"description"`
		OutTradeNo  string `json:"out_trade_no"`
		NotifyURL   string `json:"notify_url"`
		Amount      struct {
			Total    int64  `json:"total"`
			Currency string `json:"currency"`
		} `json:"amount"`
		Payer struct {
			OpenID string `json:"openid"`
		} `json:"payer"`
	}{
		AppID:       p.cfg.AppID,
		MchID:       p.cfg.MchID,
		Description: description,
		OutTradeNo:  request.OrderNo,
		NotifyURL:   p.cfg.NotifyURL,
	}
	bodyPayload.Amount.Total = request.AmountMinor
	bodyPayload.Amount.Currency = currency
	bodyPayload.Payer.OpenID = request.PayerSubject

	body, err := json.Marshal(bodyPayload)
	if err != nil {
		return ports.PaymentIntent{}, err
	}

	timestamp := fmt.Sprintf("%d", p.now().Unix())
	nonce, err := p.nonce()
	if err != nil {
		return ports.PaymentIntent{}, err
	}
	signature, err := p.sign(
		[]byte("POST\n" + weChatJSAPIPath + "\n" + timestamp + "\n" + nonce + "\n" + string(body) + "\n"),
	)
	if err != nil {
		return ports.PaymentIntent{}, err
	}
	authorization := "WECHATPAY2-SHA256-RSA2048 " +
		"mchid=\"" + p.cfg.MchID + "\"," +
		"nonce_str=\"" + nonce + "\"," +
		"signature=\"" + signature + "\"," +
		"timestamp=\"" + timestamp + "\"," +
		"serial_no=\"" + p.cfg.CertSerial + "\""

	httpRequest, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		p.cfg.APIBaseURL+weChatJSAPIPath,
		strings.NewReader(string(body)),
	)
	if err != nil {
		return ports.PaymentIntent{}, err
	}
	httpRequest.Header.Set("Authorization", authorization)
	httpRequest.Header.Set("Accept", "application/json")
	httpRequest.Header.Set("Content-Type", "application/json")
	httpRequest.Header.Set("User-Agent", "esports-companion/0.2")

	response, err := p.client.Do(httpRequest)
	if err != nil {
		return ports.PaymentIntent{}, ErrWeChatPaymentNetwork
	}
	defer response.Body.Close()

	raw, err := io.ReadAll(response.Body)
	if err != nil {
		return ports.PaymentIntent{}, ErrWeChatPaymentNetwork
	}
	var providerResponse map[string]any
	if len(raw) > 0 {
		if err := json.Unmarshal(raw, &providerResponse); err != nil {
			return ports.PaymentIntent{}, ErrWeChatPaymentInvalidJSON
		}
	} else {
		providerResponse = map[string]any{}
	}

	if response.StatusCode < 200 || response.StatusCode >= 300 {
		code := "UNKNOWN"
		if value, ok := providerResponse["code"]; ok {
			code = fmt.Sprint(value)
		}
		return ports.PaymentIntent{}, fmt.Errorf(
			"WECHAT_PAYMENT_HTTP_ERROR:%d:%s",
			response.StatusCode,
			code,
		)
	}

	prepayValue, ok := providerResponse["prepay_id"]
	if !ok {
		return ports.PaymentIntent{}, ErrWeChatPaymentInvalidResponse
	}
	prepayID, ok := prepayValue.(string)
	if !ok || strings.TrimSpace(prepayID) == "" {
		return ports.PaymentIntent{}, ErrWeChatPaymentInvalidResponse
	}

	clientTimestamp := fmt.Sprintf("%d", p.now().Unix())
	clientNonce, err := p.nonce()
	if err != nil {
		return ports.PaymentIntent{}, err
	}
	pkg := "prepay_id=" + prepayID
	paySign, err := p.sign(
		[]byte(p.cfg.AppID + "\n" + clientTimestamp + "\n" + clientNonce + "\n" + pkg + "\n"),
	)
	if err != nil {
		return ports.PaymentIntent{}, err
	}

	return ports.PaymentIntent{
		Provider:      p.Name(),
		ProviderTxnID: prepayID,
		Status:        "PENDING",
		RawPayload: map[string]any{
			"outTradeNo":       request.OrderNo,
			"prepayId":         prepayID,
			"providerResponse": providerResponse,
		},
		ClientPayload: map[string]string{
			"timeStamp": clientTimestamp,
			"nonceStr":  clientNonce,
			"package":   pkg,
			"signType":  "RSA",
			"paySign":   paySign,
		},
	}, nil
}

func (p *WeChatProvider) VerifyCallback(
	_ context.Context,
	_ map[string]string,
	_ []byte,
) (ports.PaymentCallback, error) {
	return ports.PaymentCallback{}, ErrWeChatPaymentCallbackNotMigrated
}

func (p *WeChatProvider) QueryPayment(
	_ context.Context,
	_ string,
) (ports.PaymentCallback, error) {
	return ports.PaymentCallback{}, ErrWeChatPaymentQueryNotMigrated
}

func (p *WeChatProvider) sign(message []byte) (string, error) {
	digest := sha256.Sum256(message)
	signature, err := rsa.SignPKCS1v15(
		rand.Reader,
		p.privateKey,
		crypto.SHA256,
		digest[:],
	)
	if err != nil {
		return "", err
	}
	return base64.StdEncoding.EncodeToString(signature), nil
}

func parseRSAPrivateKey(value string) (*rsa.PrivateKey, error) {
	material := strings.ReplaceAll(strings.TrimSpace(value), "\n", "
")
	block, _ := pem.Decode([]byte(material))
	if block == nil {
		return nil, ErrWeChatPaymentPrivateKeyInvalid
	}
	if parsed, err := x509.ParsePKCS8PrivateKey(block.Bytes); err == nil {
		if key, ok := parsed.(*rsa.PrivateKey); ok {
			return key, nil
		}
	}
	if key, err := x509.ParsePKCS1PrivateKey(block.Bytes); err == nil {
		return key, nil
	}
	return nil, ErrWeChatPaymentPrivateKeyInvalid
}

func randomNonce() (string, error) {
	value, err := idgen.UUIDv4()
	if err != nil {
		return "", err
	}
	return strings.ReplaceAll(value, "-", ""), nil
}
