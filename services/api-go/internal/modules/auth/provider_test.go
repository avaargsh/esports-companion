package auth

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestMockProviderMatchesReferenceIdentities(t *testing.T) {
	identity, err := (MockProvider{}).ExchangeCode(context.Background(), "demo-player-1")
	if err != nil {
		t.Fatalf("exchange mock code: %v", err)
	}
	if identity.Subject != "mock:player:1" || identity.Nickname != "Demo Player 1" {
		t.Fatalf("unexpected identity: %+v", identity)
	}
}

func TestWeChatProviderValidatesProviderResponse(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("appid") != "app" ||
			r.URL.Query().Get("secret") != "secret" ||
			r.URL.Query().Get("js_code") != "code" {
			t.Fatalf("unexpected query: %s", r.URL.RawQuery)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"openid":"openid-1","unionid":"union-1","session_key":"session-1"}`))
	}))
	defer server.Close()

	provider := WeChatProvider{
		AppID: "app", AppSecret: "secret", Endpoint: server.URL, Client: server.Client(),
	}
	identity, err := provider.ExchangeCode(context.Background(), "code")
	if err != nil {
		t.Fatalf("exchange WeChat code: %v", err)
	}
	if identity.Subject != "openid-1" || identity.UnionID != "union-1" {
		t.Fatalf("unexpected identity: %+v", identity)
	}
}

func TestWeChatProviderRejectsProviderError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"errcode":40029,"errmsg":"invalid code"}`))
	}))
	defer server.Close()

	provider := WeChatProvider{
		AppID: "app", AppSecret: "secret", Endpoint: server.URL, Client: server.Client(),
	}
	_, err := provider.ExchangeCode(context.Background(), "bad")
	if err == nil || err.Error() != "WECHAT_CODE_EXCHANGE_FAILED:40029" {
		t.Fatalf("expected provider error, got %v", err)
	}
}
