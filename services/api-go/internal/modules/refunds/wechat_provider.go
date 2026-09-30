package refunds

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
	"net/url"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/avaargsh/esports-companion/services/api-go/internal/config"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/idgen"
	"github.com/avaargsh/esports-companion/services/api-go/internal/ports"
)

const weChatRefundPath = "/v3/refund/domestic/refunds"

type httpDoer interface {
	Do(*http.Request) (*http.Response, error)
}

type WeChatProviderConfig struct {
	MchID               string
	CertSerial          string
	PrivateKey          string
	NotifyURL           string
	APIBaseURL          string
	Timeout             time.Duration
	PlatformCertSerial  string
	PlatformCertificate string
}

type WeChatProvider struct {
	cfg               WeChatProviderConfig
	privateKey        *rsa.PrivateKey
	platformPublicKey *rsa.PublicKey
	client            httpDoer
	now               func() time.Time
	nonce             func() (string, error)
}

func ProviderFromConfig(cfg config.Config) (ports.RefundProvider, error) {
	switch strings.ToLower(strings.TrimSpace(cfg.RefundProvider)) {
	case "manual":
		return ManualProvider{}, nil
	case "wechat":
		return NewWeChatProvider(WeChatProviderConfig{
			MchID:               cfg.WeChatMchID,
			CertSerial:          cfg.WeChatMchCertSerial,
			PrivateKey:          cfg.WeChatMchPrivateKey,
			NotifyURL:           cfg.WeChatRefundNotifyURL,
			APIBaseURL:          cfg.WeChatPayAPIBaseURL,
			Timeout:             cfg.WeChatPayTimeout,
			PlatformCertSerial:  cfg.WeChatPayPlatformCertSerial,
			PlatformCertificate: cfg.WeChatPayPlatformCertificate,
		})
	default:
		return nil, fmt.Errorf("%w:%s", ErrRefundProviderMissing, cfg.RefundProvider)
	}
}

func NewWeChatProvider(cfg WeChatProviderConfig) (*WeChatProvider, error) {
	required := []struct {
		name  string
		value string
	}{
		{"WECHAT_MCH_ID", cfg.MchID},
		{"WECHAT_MCH_CERT_SERIAL", cfg.CertSerial},
		{"WECHAT_MCH_PRIVATE_KEY", cfg.PrivateKey},
		{"WECHAT_REFUND_NOTIFY_URL", cfg.NotifyURL},
		{"WECHAT_PAY_PLATFORM_CERT_SERIAL", cfg.PlatformCertSerial},
		{"WECHAT_PAY_PLATFORM_CERTIFICATE", cfg.PlatformCertificate},
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
			ErrWeChatRefundCredentialsMissing,
			strings.Join(missing, ","),
		)
	}

	privateKey, err := parseRSAPrivateKey(cfg.PrivateKey)
	if err != nil {
		return nil, err
	}
	platformKey, err := parseCertificatePublicKey(cfg.PlatformCertificate)
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
			MchID:               strings.TrimSpace(cfg.MchID),
			CertSerial:          strings.TrimSpace(cfg.CertSerial),
			PrivateKey:          cfg.PrivateKey,
			NotifyURL:           strings.TrimSpace(cfg.NotifyURL),
			APIBaseURL:          baseURL,
			Timeout:             timeout,
			PlatformCertSerial:  normalizeSerial(cfg.PlatformCertSerial),
			PlatformCertificate: cfg.PlatformCertificate,
		},
		privateKey:        privateKey,
		platformPublicKey: platformKey,
		client:            &http.Client{Timeout: timeout},
		now:               time.Now,
		nonce:             randomNonce,
	}, nil
}

func (p *WeChatProvider) Name() string {
	return "WECHAT"
}

func (p *WeChatProvider) CreateRefund(
	ctx context.Context,
	request ports.RefundRequest,
) (ports.RefundIntent, error) {
	if strings.TrimSpace(request.PaymentTxnID) == "" {
		return ports.RefundIntent{}, ErrWeChatPaymentTxnMissing
	}
	if strings.TrimSpace(request.OutRefundNo) == "" {
		return ports.RefundIntent{}, ErrRefundOutRefundNoMissing
	}
	currency := strings.ToUpper(strings.TrimSpace(request.Currency))
	if currency == "" {
		currency = "CNY"
	}
	reason := truncateUTF8(request.Reason, 80)
	if reason == "" {
		reason = "Dispute refund"
	}

	bodyPayload := struct {
		TransactionID string `json:"transaction_id"`
		OutRefundNo   string `json:"out_refund_no"`
		Reason        string `json:"reason"`
		NotifyURL     string `json:"notify_url"`
		Amount        struct {
			Refund   int64  `json:"refund"`
			Total    int64  `json:"total"`
			Currency string `json:"currency"`
		} `json:"amount"`
	}{
		TransactionID: request.PaymentTxnID,
		OutRefundNo:   request.OutRefundNo,
		Reason:        reason,
		NotifyURL:     p.cfg.NotifyURL,
	}
	bodyPayload.Amount.Refund = request.RefundAmount
	bodyPayload.Amount.Total = request.TotalAmount
	bodyPayload.Amount.Currency = currency

	body, err := json.Marshal(bodyPayload)
	if err != nil {
		return ports.RefundIntent{}, err
	}
	timestamp := fmt.Sprintf("%d", p.now().Unix())
	nonce, err := p.nonce()
	if err != nil {
		return ports.RefundIntent{}, err
	}
	signature, err := p.sign(
		[]byte("POST\n" + weChatRefundPath + "\n" + timestamp + "\n" + nonce + "\n" + string(body) + "\n"),
	)
	if err != nil {
		return ports.RefundIntent{}, err
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
		p.cfg.APIBaseURL+weChatRefundPath,
		strings.NewReader(string(body)),
	)
	if err != nil {
		return ports.RefundIntent{}, err
	}
	httpRequest.Header.Set("Authorization", authorization)
	httpRequest.Header.Set("Accept", "application/json")
	httpRequest.Header.Set("Content-Type", "application/json")
	httpRequest.Header.Set("User-Agent", "esports-companion/0.2")

	response, err := p.client.Do(httpRequest)
	if err != nil {
		return ports.RefundIntent{}, ErrWeChatRefundNetwork
	}
	defer response.Body.Close()

	raw, err := io.ReadAll(response.Body)
	if err != nil {
		return ports.RefundIntent{}, ErrWeChatRefundNetwork
	}
	var payload map[string]any
	if len(raw) > 0 {
		if err := json.Unmarshal(raw, &payload); err != nil {
			return ports.RefundIntent{}, ErrWeChatRefundInvalidJSON
		}
	} else {
		payload = map[string]any{}
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		code := "UNKNOWN"
		if value, ok := payload["code"]; ok {
			code = fmt.Sprint(value)
		}
		return ports.RefundIntent{}, fmt.Errorf(
			"%w:%d:%s",
			ErrWeChatRefundHTTP,
			response.StatusCode,
			code,
		)
	}
	if err := p.verifyResponseSignature(response.Header, raw); err != nil {
		return ports.RefundIntent{}, err
	}

	refundID, _ := payload["refund_id"].(string)
	outRefundNo, _ := payload["out_refund_no"].(string)
	status := strings.ToUpper(fmt.Sprint(payload["status"]))
	if strings.TrimSpace(refundID) == "" || outRefundNo != request.OutRefundNo {
		return ports.RefundIntent{}, ErrWeChatRefundInvalidResponse
	}
	switch status {
	case "SUCCESS", "PROCESSING", "CLOSED", "ABNORMAL":
	default:
		return ports.RefundIntent{}, ErrWeChatRefundStatusInvalid
	}
	return ports.RefundIntent{
		Provider:         p.Name(),
		ProviderRefundID: refundID,
		Status:           status,
		RawPayload:       payload,
	}, nil
}

func (p *WeChatProvider) QueryRefund(
	ctx context.Context,
	outRefundNo string,
) (ports.RefundIntent, error) {
	outRefundNo = strings.TrimSpace(outRefundNo)
	if outRefundNo == "" {
		return ports.RefundIntent{}, ErrRefundOutRefundNoMissing
	}
	path := "/v3/refund/domestic/refunds/" + url.PathEscape(outRefundNo)
	timestamp := fmt.Sprintf("%d", p.now().Unix())
	nonce, err := p.nonce()
	if err != nil {
		return ports.RefundIntent{}, err
	}
	signature, err := p.sign(
		[]byte("GET\n" + path + "\n" + timestamp + "\n" + nonce + "\n\n"),
	)
	if err != nil {
		return ports.RefundIntent{}, err
	}
	authorization := "WECHATPAY2-SHA256-RSA2048 " +
		"mchid=\"" + p.cfg.MchID + "\"," +
		"nonce_str=\"" + nonce + "\"," +
		"signature=\"" + signature + "\"," +
		"timestamp=\"" + timestamp + "\"," +
		"serial_no=\"" + p.cfg.CertSerial + "\""

	request, err := http.NewRequestWithContext(
		ctx,
		http.MethodGet,
		p.cfg.APIBaseURL+path,
		nil,
	)
	if err != nil {
		return ports.RefundIntent{}, err
	}
	request.Header.Set("Authorization", authorization)
	request.Header.Set("Accept", "application/json")
	request.Header.Set("User-Agent", "esports-companion/0.2")

	response, err := p.client.Do(request)
	if err != nil {
		return ports.RefundIntent{}, ErrWeChatRefundQueryNetwork
	}
	defer response.Body.Close()

	raw, err := io.ReadAll(response.Body)
	if err != nil {
		return ports.RefundIntent{}, ErrWeChatRefundQueryNetwork
	}
	var payload map[string]any
	if len(raw) > 0 {
		if err := json.Unmarshal(raw, &payload); err != nil {
			return ports.RefundIntent{}, ErrWeChatRefundQueryInvalidJSON
		}
	} else {
		payload = map[string]any{}
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		code := "UNKNOWN"
		if value, ok := payload["code"]; ok {
			code = fmt.Sprint(value)
		}
		return ports.RefundIntent{}, fmt.Errorf(
			"%w:%d:%s",
			ErrWeChatRefundQueryHTTP,
			response.StatusCode,
			code,
		)
	}
	if err := p.verifyResponseSignature(response.Header, raw); err != nil {
		return ports.RefundIntent{}, err
	}

	providerRefundID, _ := payload["refund_id"].(string)
	responseOutRefundNo, _ := payload["out_refund_no"].(string)
	status := strings.ToUpper(fmt.Sprint(payload["status"]))
	if strings.TrimSpace(providerRefundID) == "" || responseOutRefundNo != outRefundNo {
		return ports.RefundIntent{}, ErrWeChatRefundQueryInvalidResponse
	}
	switch status {
	case "SUCCESS", "PROCESSING", "CLOSED", "ABNORMAL":
	default:
		return ports.RefundIntent{}, ErrWeChatRefundStatusInvalid
	}
	return ports.RefundIntent{
		Provider:         p.Name(),
		ProviderRefundID: providerRefundID,
		Status:           status,
		RawPayload:       payload,
	}, nil
}

func (p *WeChatProvider) verifyResponseSignature(
	headers http.Header,
	body []byte,
) error {
	timestamp := headers.Get("Wechatpay-Timestamp")
	nonce := headers.Get("Wechatpay-Nonce")
	signature := headers.Get("Wechatpay-Signature")
	serial := headers.Get("Wechatpay-Serial")
	if timestamp == "" || nonce == "" || signature == "" || serial == "" {
		return ErrWeChatRefundSignatureHeaders
	}
	if normalizeSerial(serial) != p.cfg.PlatformCertSerial {
		return ErrWeChatRefundSerialUnknown
	}
	decoded, err := base64.StdEncoding.DecodeString(signature)
	if err != nil {
		return ErrWeChatRefundSignatureInvalid
	}
	message := []byte(timestamp + "\n" + nonce + "\n" + string(body) + "\n")
	digest := sha256.Sum256(message)
	if err := rsa.VerifyPKCS1v15(
		p.platformPublicKey,
		crypto.SHA256,
		digest[:],
		decoded,
	); err != nil {
		return ErrWeChatRefundSignatureInvalid
	}
	return nil
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
	material := strings.ReplaceAll(strings.TrimSpace(value), "\\n", "\n")
	block, _ := pem.Decode([]byte(material))
	if block == nil {
		return nil, ErrWeChatRefundPrivateKeyInvalid
	}
	if parsed, err := x509.ParsePKCS8PrivateKey(block.Bytes); err == nil {
		if key, ok := parsed.(*rsa.PrivateKey); ok {
			return key, nil
		}
	}
	if key, err := x509.ParsePKCS1PrivateKey(block.Bytes); err == nil {
		return key, nil
	}
	return nil, ErrWeChatRefundPrivateKeyInvalid
}

func parseCertificatePublicKey(value string) (*rsa.PublicKey, error) {
	material := strings.ReplaceAll(strings.TrimSpace(value), "\\n", "\n")
	block, _ := pem.Decode([]byte(material))
	if block == nil {
		return nil, ErrWeChatRefundCertificateInvalid
	}
	certificate, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		return nil, ErrWeChatRefundCertificateInvalid
	}
	publicKey, ok := certificate.PublicKey.(*rsa.PublicKey)
	if !ok {
		return nil, ErrWeChatRefundCertificateInvalid
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

func randomNonce() (string, error) {
	value, err := idgen.UUIDv4()
	if err != nil {
		return "", err
	}
	return strings.ReplaceAll(value, "-", ""), nil
}

func truncateUTF8(value string, limit int) string {
	if len(value) <= limit {
		return value
	}
	data := []byte(value)
	if len(data) <= limit {
		return value
	}
	data = data[:limit]
	for len(data) > 0 && !utf8.Valid(data) {
		data = data[:len(data)-1]
	}
	return string(data)
}
