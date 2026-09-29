package auth

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/avaargsh/esports-companion/services/api-go/internal/config"
	"github.com/avaargsh/esports-companion/services/api-go/internal/ports"
)

const code2SessionURL = "https://api.weixin.qq.com/sns/jscode2session"

type MockProvider struct{}

func (MockProvider) Name() string { return "MOCK" }

func (MockProvider) ExchangeCode(_ context.Context, code string) (ports.Identity, error) {
	identities := map[string]ports.Identity{
		"demo-customer": {
			Provider: "MOCK", Subject: "mock:customer", Nickname: "Demo Customer",
			SessionKey: "mock-session:customer",
		},
		"demo-player-1": {
			Provider: "MOCK", Subject: "mock:player:1", Nickname: "Demo Player 1",
			SessionKey: "mock-session:player:1",
		},
		"demo-player-2": {
			Provider: "MOCK", Subject: "mock:player:2", Nickname: "Demo Player 2",
			SessionKey: "mock-session:player:2",
		},
		"demo-player-3": {
			Provider: "MOCK", Subject: "mock:player:3", Nickname: "Demo Player 3",
			SessionKey: "mock-session:player:3",
		},
		"demo-platform": {
			Provider: "MOCK", Subject: "mock:platform", Nickname: "Platform",
			SessionKey: "mock-session:platform",
		},
	}
	identity, ok := identities[code]
	if !ok {
		return ports.Identity{}, errors.New("INVALID_MOCK_LOGIN_CODE")
	}
	return identity, nil
}

type WeChatProvider struct {
	AppID     string
	AppSecret string
	Endpoint  string
	Client    *http.Client
}

func (WeChatProvider) Name() string { return "WECHAT" }

func (p WeChatProvider) ExchangeCode(ctx context.Context, code string) (ports.Identity, error) {
	if strings.TrimSpace(code) == "" {
		return ports.Identity{}, errors.New("WECHAT_LOGIN_CODE_REQUIRED")
	}
	if p.AppID == "" || p.AppSecret == "" {
		return ports.Identity{}, errors.New("WECHAT_AUTH_CREDENTIALS_MISSING")
	}

	endpoint := p.Endpoint
	if endpoint == "" {
		endpoint = code2SessionURL
	}
	client := p.Client
	if client == nil {
		client = &http.Client{Timeout: 5 * time.Second}
	}

	query := url.Values{
		"appid":      {p.AppID},
		"secret":     {p.AppSecret},
		"js_code":    {code},
		"grant_type": {"authorization_code"},
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint+"?"+query.Encode(), nil)
	if err != nil {
		return ports.Identity{}, errors.New("WECHAT_CODE_EXCHANGE_NETWORK_ERROR")
	}
	resp, err := client.Do(req)
	if err != nil {
		return ports.Identity{}, errors.New("WECHAT_CODE_EXCHANGE_NETWORK_ERROR")
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return ports.Identity{}, fmt.Errorf("WECHAT_CODE_EXCHANGE_HTTP_ERROR:%d", resp.StatusCode)
	}

	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return ports.Identity{}, errors.New("WECHAT_CODE_EXCHANGE_NETWORK_ERROR")
	}

	var payload struct {
		OpenID     string `json:"openid"`
		UnionID    string `json:"unionid"`
		SessionKey string `json:"session_key"`
		ErrCode    int    `json:"errcode"`
	}
	if err := json.Unmarshal(body, &payload); err != nil {
		return ports.Identity{}, errors.New("WECHAT_CODE_EXCHANGE_INVALID_JSON")
	}
	if payload.ErrCode != 0 {
		return ports.Identity{}, fmt.Errorf("WECHAT_CODE_EXCHANGE_FAILED:%d", payload.ErrCode)
	}
	if payload.OpenID == "" || payload.SessionKey == "" {
		return ports.Identity{}, errors.New("WECHAT_CODE_EXCHANGE_INVALID_RESPONSE")
	}
	return ports.Identity{
		Provider:   "WECHAT",
		Subject:    payload.OpenID,
		UnionID:    payload.UnionID,
		SessionKey: payload.SessionKey,
	}, nil
}

type unavailableProvider struct {
	name string
}

func (p unavailableProvider) Name() string { return strings.ToUpper(p.name) }
func (p unavailableProvider) ExchangeCode(context.Context, string) (ports.Identity, error) {
	return ports.Identity{}, fmt.Errorf("AUTH_PROVIDER_NOT_CONFIGURED:%s", p.name)
}

func NewProvider(cfg config.Config) ports.AuthProvider {
	switch cfg.AuthProvider {
	case "mock":
		return MockProvider{}
	case "wechat":
		return WeChatProvider{
			AppID:     cfg.WeChatAppID,
			AppSecret: cfg.WeChatAppSecret,
			Client:    &http.Client{Timeout: cfg.WeChatAuthTimeout},
		}
	default:
		return unavailableProvider{name: cfg.AuthProvider}
	}
}
