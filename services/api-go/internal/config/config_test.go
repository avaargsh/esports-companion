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
