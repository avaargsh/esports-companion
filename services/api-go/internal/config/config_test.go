package config

import (
	"strings"
	"testing"
)

func TestDevDefaultsAreValid(t *testing.T) {
	t.Setenv("APP_ENV", "dev")
	t.Setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/db")
	t.Setenv("REDIS_URL", "redis://localhost:6379/0")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("load dev config: %v", err)
	}
	if !strings.HasPrefix(cfg.DatabaseURL, "postgresql://") {
		t.Fatalf("expected pgx-compatible DSN, got %s", cfg.DatabaseURL)
	}
}

func TestProductionRejectsMockProviders(t *testing.T) {
	t.Setenv("APP_ENV", "production")
	t.Setenv("AUTH_PROVIDER", "mock")
	t.Setenv("PAYMENT_PROVIDER", "mock")
	t.Setenv("SESSION_SIGNING_KEY", "01234567890123456789012345678901")

	_, err := Load()
	if err == nil || !strings.Contains(err.Error(), "AUTH_PROVIDER_MUST_BE_WECHAT") {
		t.Fatalf("expected fail-closed production config, got %v", err)
	}
}

func TestRefreshTTLMustExceedAccessTTL(t *testing.T) {
	t.Setenv("APP_ENV", "dev")
	t.Setenv("ACCESS_TOKEN_TTL_SECONDS", "900")
	t.Setenv("REFRESH_TOKEN_TTL_SECONDS", "900")

	_, err := Load()
	if err == nil || !strings.Contains(err.Error(), "REFRESH_TOKEN_TTL_MUST_EXCEED_ACCESS_TOKEN_TTL") {
		t.Fatalf("expected session TTL validation, got %v", err)
	}
}

func TestSecureDeploymentRequiresWeChatCredentials(t *testing.T) {
	t.Setenv("APP_ENV", "staging")
	t.Setenv("AUTH_PROVIDER", "wechat")
	t.Setenv("PAYMENT_PROVIDER", "wechat")
	t.Setenv("REFUND_PROVIDER", "manual")
	t.Setenv("SESSION_SIGNING_KEY", "01234567890123456789012345678901")
	t.Setenv("WECHAT_APP_ID", "")
	t.Setenv("WECHAT_APP_SECRET", "")

	_, err := Load()
	if err == nil || !strings.Contains(err.Error(), "WECHAT_APP_ID_REQUIRED") ||
		!strings.Contains(err.Error(), "WECHAT_APP_SECRET_REQUIRED") {
		t.Fatalf("expected WeChat credential validation, got %v", err)
	}
}
