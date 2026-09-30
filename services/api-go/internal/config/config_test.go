package config

import (
	"strings"
	"testing"
	"time"
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

func TestSecureDeploymentRequiresPaymentCredentials(t *testing.T) {
	t.Setenv("APP_ENV", "staging")
	t.Setenv("AUTH_PROVIDER", "wechat")
	t.Setenv("PAYMENT_PROVIDER", "wechat")
	t.Setenv("REFUND_PROVIDER", "manual")
	t.Setenv("SESSION_SIGNING_KEY", "01234567890123456789012345678901")
	t.Setenv("WECHAT_APP_ID", "wx-test")
	t.Setenv("WECHAT_APP_SECRET", "secret")
	t.Setenv("WECHAT_MCH_ID", "")
	t.Setenv("WECHAT_MCH_CERT_SERIAL", "")
	t.Setenv("WECHAT_MCH_PRIVATE_KEY", "")
	t.Setenv("WECHAT_NOTIFY_URL", "")

	_, err := Load()
	if err == nil ||
		!strings.Contains(err.Error(), "WECHAT_MCH_ID_REQUIRED") ||
		!strings.Contains(err.Error(), "WECHAT_MCH_CERT_SERIAL_REQUIRED") ||
		!strings.Contains(err.Error(), "WECHAT_MCH_PRIVATE_KEY_REQUIRED") ||
		!strings.Contains(err.Error(), "WECHAT_NOTIFY_URL_REQUIRED") {
		t.Fatalf("expected WeChat payment credential validation, got %v", err)
	}
}

func TestSecureDeploymentRejectsNonPublicNotifyURL(t *testing.T) {
	cfg := Config{
		AppEnv:                       "staging",
		DatabaseURL:                  "postgresql://u:p@db:5432/app",
		RedisURL:                     "redis://redis:6379/0",
		DatabaseMaxConns:             4,
		DatabaseMinConns:             1,
		RedisPoolSize:                4,
		ReadinessRequireRedis:        true,
		AuthProvider:                 "wechat",
		PaymentProvider:              "wechat",
		RefundProvider:               "manual",
		SessionSigningKey:            "01234567890123456789012345678901",
		AccessTokenTTLSeconds:        900,
		RefreshTokenTTLSeconds:       3600,
		WeChatAppID:                  "wx-test",
		WeChatAppSecret:              "secret",
		WeChatAuthTimeout:            time.Second,
		WeChatMchID:                  "mch",
		WeChatMchCertSerial:          "serial",
		WeChatMchPrivateKey:          "key",
		WeChatNotifyURL:              "http://127.0.0.1/callback",
		WeChatPayAPIV3Key:            "01234567890123456789012345678901",
		WeChatPayPlatformCertSerial:  "platform-serial",
		WeChatPayPlatformCertificate: "certificate",
		WeChatPayTimeout:             time.Second,
		OutboxPollInterval:           500 * time.Millisecond,
		OutboxBatchSize:              50,
		ShutdownTimeout:              time.Second,
	}
	err := cfg.Validate()
	if err == nil || !strings.Contains(err.Error(), "WECHAT_NOTIFY_URL_MUST_BE_PUBLIC_HTTPS") {
		t.Fatalf("expected public HTTPS notify validation, got %v", err)
	}
}

func TestOutboxWorkerConfigMustBePositive(t *testing.T) {
	t.Setenv("APP_ENV", "dev")
	t.Setenv("OUTBOX_POLL_INTERVAL_MS", "0")

	_, err := Load()
	if err == nil || !strings.Contains(err.Error(), "OUTBOX_POLL_INTERVAL_MUST_BE_POSITIVE") {
		t.Fatalf("expected outbox poll interval validation, got %v", err)
	}

	t.Setenv("OUTBOX_POLL_INTERVAL_MS", "500")
	t.Setenv("OUTBOX_BATCH_SIZE", "501")
	_, err = Load()
	if err == nil || !strings.Contains(err.Error(), "OUTBOX_BATCH_SIZE_INVALID") {
		t.Fatalf("expected outbox batch validation, got %v", err)
	}
}
