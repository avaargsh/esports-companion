package config

import (
	"errors"
	"fmt"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

const devSigningKey = "dev-only-change-me-use-at-least-32-bytes"

type Config struct {
	AppEnv                         string
	ServiceName                    string
	CommitSHA                      string
	LogLevel                       string
	HTTPAddr                       string
	WorkerMetricsAddr              string
	DatabaseURL                    string
	RedisURL                       string
	DatabaseMaxConns               int32
	DatabaseMinConns               int32
	RedisPoolSize                  int
	ReadinessRequireRedis          bool
	AuthProvider                   string
	PaymentProvider                string
	RefundProvider                 string
	SessionSigningKey              string
	AccessTokenTTLSeconds          int
	RefreshTokenTTLSeconds         int
	WeChatAppID                    string
	WeChatAppSecret                string
	WeChatAuthTimeout              time.Duration
	WeChatMchID                    string
	WeChatMchCertSerial            string
	WeChatMchPrivateKey            string
	WeChatNotifyURL                string
	WeChatRefundNotifyURL          string
	WeChatPayAPIBaseURL            string
	WeChatPayAPIV3Key              string
	WeChatPayPlatformCertSerial    string
	WeChatPayPlatformCertificate   string
	WeChatPayTimeout               time.Duration
	OutboxPollInterval             time.Duration
	OutboxBatchSize                int
	FinishConfirmTimeout           time.Duration
	AssignmentStartTimeout         time.Duration
	OrderTimeoutScanInterval       time.Duration
	OrderTimeoutBatchSize          int
	RefundReconcileScanInterval    time.Duration
	RefundReconcileMinAge          time.Duration
	RefundReconcileBatchSize       int
	OperationalMetricsScanInterval time.Duration
	ShutdownTimeout                time.Duration
}

func Load() (Config, error) {
	databaseURL, err := valueOrFile(
		env("DATABASE_URL", "postgresql://esports:esports@postgres:5432/esports"),
		os.Getenv("DATABASE_URL_FILE"),
	)
	if err != nil {
		return Config{}, fmt.Errorf("database url: %w", err)
	}
	databaseURL = strings.Replace(databaseURL, "postgresql+psycopg://", "postgresql://", 1)

	redisURL, err := valueOrFile(
		env("REDIS_URL", "redis://redis:6379/0"),
		os.Getenv("REDIS_URL_FILE"),
	)
	if err != nil {
		return Config{}, fmt.Errorf("redis url: %w", err)
	}
	signingKey, err := valueOrFile(
		env("SESSION_SIGNING_KEY", devSigningKey),
		os.Getenv("SESSION_SIGNING_KEY_FILE"),
	)
	if err != nil {
		return Config{}, fmt.Errorf("session signing key: %w", err)
	}
	wechatSecret, err := valueOrFile(
		env("WECHAT_APP_SECRET", ""),
		os.Getenv("WECHAT_APP_SECRET_FILE"),
	)
	if err != nil {
		return Config{}, fmt.Errorf("wechat app secret: %w", err)
	}

	wechatMchPrivateKey, err := valueOrFile(
		env("WECHAT_MCH_PRIVATE_KEY", ""),
		os.Getenv("WECHAT_MCH_PRIVATE_KEY_FILE"),
	)
	if err != nil {
		return Config{}, fmt.Errorf("wechat merchant private key: %w", err)
	}
	wechatAPIV3Key, err := valueOrFile(
		env("WECHAT_PAY_API_V3_KEY", ""),
		os.Getenv("WECHAT_PAY_API_V3_KEY_FILE"),
	)
	if err != nil {
		return Config{}, fmt.Errorf("wechat api v3 key: %w", err)
	}
	wechatPlatformCertificate, err := valueOrFile(
		env("WECHAT_PAY_PLATFORM_CERTIFICATE", ""),
		os.Getenv("WECHAT_PAY_PLATFORM_CERTIFICATE_FILE"),
	)
	if err != nil {
		return Config{}, fmt.Errorf("wechat platform certificate: %w", err)
	}

	maxConns, err := envInt("DATABASE_MAX_CONNS", 32)
	if err != nil {
		return Config{}, err
	}
	minConns, err := envInt("DATABASE_MIN_CONNS", 4)
	if err != nil {
		return Config{}, err
	}
	redisPoolSize, err := envInt("REDIS_POOL_SIZE", 64)
	if err != nil {
		return Config{}, err
	}
	requireRedis, err := envBool("READINESS_REQUIRE_REDIS", true)
	if err != nil {
		return Config{}, err
	}
	accessTTL, err := envInt("ACCESS_TOKEN_TTL_SECONDS", 900)
	if err != nil {
		return Config{}, err
	}
	refreshTTL, err := envInt("REFRESH_TOKEN_TTL_SECONDS", 2592000)
	if err != nil {
		return Config{}, err
	}
	wechatTimeoutSeconds, err := envInt("WECHAT_AUTH_TIMEOUT_SECONDS", 5)
	if err != nil {
		return Config{}, err
	}
	wechatPayTimeoutSeconds, err := envInt("WECHAT_PAY_TIMEOUT_SECONDS", 8)
	if err != nil {
		return Config{}, err
	}
	outboxPollMilliseconds, err := envInt("OUTBOX_POLL_INTERVAL_MS", 500)
	if err != nil {
		return Config{}, err
	}
	outboxBatchSize, err := envInt("OUTBOX_BATCH_SIZE", 50)
	if err != nil {
		return Config{}, err
	}
	finishConfirmSeconds, err := envInt("FINISH_CONFIRM_TIMEOUT_SECONDS", 1800)
	if err != nil {
		return Config{}, err
	}
	assignmentStartSeconds, err := envInt("ASSIGNMENT_START_TIMEOUT_SECONDS", 600)
	if err != nil {
		return Config{}, err
	}
	orderTimeoutScanSeconds, err := envInt("ORDER_TIMEOUT_SCAN_SECONDS", 30)
	if err != nil {
		return Config{}, err
	}
	orderTimeoutBatchSize, err := envInt("ORDER_TIMEOUT_BATCH_SIZE", 50)
	if err != nil {
		return Config{}, err
	}
	refundReconcileScanSeconds, err := envInt("REFUND_RECONCILE_SCAN_SECONDS", 60)
	if err != nil {
		return Config{}, err
	}
	refundReconcileMinAgeSeconds, err := envInt("REFUND_RECONCILE_MIN_AGE_SECONDS", 30)
	if err != nil {
		return Config{}, err
	}
	refundReconcileBatchSize, err := envInt("REFUND_RECONCILE_BATCH_SIZE", 20)
	if err != nil {
		return Config{}, err
	}
	operationalMetricsScanSeconds, err := envInt("OPERATIONAL_METRICS_SCAN_SECONDS", 15)
	if err != nil {
		return Config{}, err
	}
	shutdownSeconds, err := envInt("SHUTDOWN_TIMEOUT_SECONDS", 15)
	if err != nil {
		return Config{}, err
	}

	cfg := Config{
		AppEnv:                         strings.ToLower(strings.TrimSpace(env("APP_ENV", "dev"))),
		ServiceName:                    env("SERVICE_NAME", "esports-companion-api-go"),
		CommitSHA:                      env("COMMIT_SHA", "dev"),
		LogLevel:                       strings.ToUpper(env("LOG_LEVEL", "INFO")),
		HTTPAddr:                       env("API_GO_HTTP_ADDR", ":8080"),
		WorkerMetricsAddr:              env("WORKER_METRICS_ADDR", ":9091"),
		DatabaseURL:                    databaseURL,
		RedisURL:                       redisURL,
		DatabaseMaxConns:               int32(maxConns),
		DatabaseMinConns:               int32(minConns),
		RedisPoolSize:                  redisPoolSize,
		ReadinessRequireRedis:          requireRedis,
		AuthProvider:                   strings.ToLower(env("AUTH_PROVIDER", "mock")),
		PaymentProvider:                strings.ToLower(env("PAYMENT_PROVIDER", "mock")),
		RefundProvider:                 strings.ToLower(env("REFUND_PROVIDER", "manual")),
		SessionSigningKey:              signingKey,
		AccessTokenTTLSeconds:          accessTTL,
		RefreshTokenTTLSeconds:         refreshTTL,
		WeChatAppID:                    env("WECHAT_APP_ID", ""),
		WeChatAppSecret:                wechatSecret,
		WeChatAuthTimeout:              time.Duration(wechatTimeoutSeconds) * time.Second,
		WeChatMchID:                    env("WECHAT_MCH_ID", ""),
		WeChatMchCertSerial:            env("WECHAT_MCH_CERT_SERIAL", ""),
		WeChatMchPrivateKey:            wechatMchPrivateKey,
		WeChatNotifyURL:                env("WECHAT_NOTIFY_URL", ""),
		WeChatRefundNotifyURL:          env("WECHAT_REFUND_NOTIFY_URL", ""),
		WeChatPayAPIBaseURL:            env("WECHAT_PAY_API_BASE_URL", "https://api.mch.weixin.qq.com"),
		WeChatPayAPIV3Key:              wechatAPIV3Key,
		WeChatPayPlatformCertSerial:    env("WECHAT_PAY_PLATFORM_CERT_SERIAL", ""),
		WeChatPayPlatformCertificate:   wechatPlatformCertificate,
		WeChatPayTimeout:               time.Duration(wechatPayTimeoutSeconds) * time.Second,
		OutboxPollInterval:             time.Duration(outboxPollMilliseconds) * time.Millisecond,
		OutboxBatchSize:                outboxBatchSize,
		FinishConfirmTimeout:           time.Duration(finishConfirmSeconds) * time.Second,
		AssignmentStartTimeout:         time.Duration(assignmentStartSeconds) * time.Second,
		OrderTimeoutScanInterval:       time.Duration(orderTimeoutScanSeconds) * time.Second,
		OrderTimeoutBatchSize:          orderTimeoutBatchSize,
		RefundReconcileScanInterval:    time.Duration(refundReconcileScanSeconds) * time.Second,
		RefundReconcileMinAge:          time.Duration(refundReconcileMinAgeSeconds) * time.Second,
		RefundReconcileBatchSize:       refundReconcileBatchSize,
		OperationalMetricsScanInterval: time.Duration(operationalMetricsScanSeconds) * time.Second,
		ShutdownTimeout:                time.Duration(shutdownSeconds) * time.Second,
	}

	if err := cfg.Validate(); err != nil {
		return Config{}, err
	}
	return cfg, nil
}

func (c Config) SecureDeployment() bool {
	return c.AppEnv == "staging" || c.AppEnv == "prod" || c.AppEnv == "production"
}

func (c Config) IsSecureDeployment() bool {
	return c.SecureDeployment()
}

func (c Config) Validate() error {
	if c.DatabaseURL == "" {
		return errors.New("DATABASE_URL_REQUIRED")
	}
	if c.RedisURL == "" && c.ReadinessRequireRedis {
		return errors.New("REDIS_URL_REQUIRED")
	}
	if c.DatabaseMaxConns <= 0 || c.DatabaseMinConns < 0 || c.DatabaseMinConns > c.DatabaseMaxConns {
		return errors.New("DATABASE_POOL_INVALID")
	}
	if c.RedisPoolSize <= 0 {
		return errors.New("REDIS_POOL_SIZE_INVALID")
	}
	if c.AccessTokenTTLSeconds <= 0 {
		return errors.New("ACCESS_TOKEN_TTL_MUST_BE_POSITIVE")
	}
	if c.RefreshTokenTTLSeconds <= c.AccessTokenTTLSeconds {
		return errors.New("REFRESH_TOKEN_TTL_MUST_EXCEED_ACCESS_TOKEN_TTL")
	}
	if c.WeChatAuthTimeout <= 0 {
		return errors.New("WECHAT_AUTH_TIMEOUT_MUST_BE_POSITIVE")
	}
	if c.WeChatPayTimeout <= 0 {
		return errors.New("WECHAT_PAY_TIMEOUT_MUST_BE_POSITIVE")
	}
	if c.OutboxPollInterval <= 0 {
		return errors.New("OUTBOX_POLL_INTERVAL_MUST_BE_POSITIVE")
	}
	if c.OutboxBatchSize <= 0 || c.OutboxBatchSize > 500 {
		return errors.New("OUTBOX_BATCH_SIZE_INVALID")
	}
	if c.FinishConfirmTimeout <= 0 {
		return errors.New("FINISH_CONFIRM_TIMEOUT_MUST_BE_POSITIVE")
	}
	if c.AssignmentStartTimeout <= 0 {
		return errors.New("ASSIGNMENT_START_TIMEOUT_MUST_BE_POSITIVE")
	}
	if c.OrderTimeoutScanInterval <= 0 {
		return errors.New("ORDER_TIMEOUT_SCAN_MUST_BE_POSITIVE")
	}
	if c.OrderTimeoutBatchSize <= 0 || c.OrderTimeoutBatchSize > 500 {
		return errors.New("ORDER_TIMEOUT_BATCH_SIZE_INVALID")
	}
	if c.RefundReconcileScanInterval <= 0 {
		return errors.New("REFUND_RECONCILE_SCAN_MUST_BE_POSITIVE")
	}
	if c.RefundReconcileMinAge < 0 {
		return errors.New("REFUND_RECONCILE_MIN_AGE_MUST_NOT_BE_NEGATIVE")
	}
	if c.RefundReconcileBatchSize <= 0 || c.RefundReconcileBatchSize > 500 {
		return errors.New("REFUND_RECONCILE_BATCH_SIZE_INVALID")
	}
	if strings.TrimSpace(c.WorkerMetricsAddr) == "" {
		return errors.New("WORKER_METRICS_ADDR_REQUIRED")
	}
	if c.OperationalMetricsScanInterval <= 0 {
		return errors.New("OPERATIONAL_METRICS_SCAN_MUST_BE_POSITIVE")
	}
	if c.ShutdownTimeout <= 0 {
		return errors.New("SHUTDOWN_TIMEOUT_INVALID")
	}

	if c.SecureDeployment() {
		var violations []string
		if c.AuthProvider != "wechat" {
			violations = append(violations, "AUTH_PROVIDER_MUST_BE_WECHAT")
		}
		if c.PaymentProvider != "wechat" {
			violations = append(violations, "PAYMENT_PROVIDER_MUST_BE_WECHAT")
		}
		if c.RefundProvider != "wechat" && c.RefundProvider != "manual" {
			violations = append(violations, "REFUND_PROVIDER_INVALID")
		}
		if c.SessionSigningKey == devSigningKey || len(c.SessionSigningKey) < 32 {
			violations = append(violations, "SESSION_SIGNING_KEY_WEAK")
		}
		if c.WeChatAppID == "" {
			violations = append(violations, "WECHAT_APP_ID_REQUIRED")
		}
		if c.WeChatAppSecret == "" {
			violations = append(violations, "WECHAT_APP_SECRET_REQUIRED")
		}
		required := map[string]string{
			"WECHAT_MCH_ID":                   c.WeChatMchID,
			"WECHAT_MCH_CERT_SERIAL":          c.WeChatMchCertSerial,
			"WECHAT_MCH_PRIVATE_KEY":          c.WeChatMchPrivateKey,
			"WECHAT_NOTIFY_URL":               c.WeChatNotifyURL,
			"WECHAT_PAY_API_V3_KEY":           c.WeChatPayAPIV3Key,
			"WECHAT_PAY_PLATFORM_CERT_SERIAL": c.WeChatPayPlatformCertSerial,
			"WECHAT_PAY_PLATFORM_CERTIFICATE": c.WeChatPayPlatformCertificate,
		}
		if c.RefundProvider == "wechat" {
			required["WECHAT_REFUND_NOTIFY_URL"] = c.WeChatRefundNotifyURL
		}
		for name, value := range required {
			if strings.TrimSpace(value) == "" {
				violations = append(violations, name+"_REQUIRED")
			}
		}
		if c.WeChatNotifyURL != "" && !isPublicHTTPS(c.WeChatNotifyURL) {
			violations = append(violations, "WECHAT_NOTIFY_URL_MUST_BE_PUBLIC_HTTPS")
		}
		if c.WeChatRefundNotifyURL != "" && !isPublicHTTPS(c.WeChatRefundNotifyURL) {
			violations = append(violations, "WECHAT_REFUND_NOTIFY_URL_MUST_BE_PUBLIC_HTTPS")
		}
		if len(violations) > 0 {
			return fmt.Errorf("SECURE_CONFIG_INVALID:%s", strings.Join(violations, ","))
		}
	}
	return nil
}

func valueOrFile(value, file string) (string, error) {
	if strings.TrimSpace(file) == "" {
		return strings.TrimSpace(value), nil
	}
	content, err := os.ReadFile(strings.TrimSpace(file))
	if err != nil {
		return "", err
	}
	resolved := strings.TrimSpace(string(content))
	if resolved == "" {
		return "", errors.New("SECRET_FILE_EMPTY")
	}
	return resolved, nil
}

func env(name, fallback string) string {
	if value, ok := os.LookupEnv(name); ok {
		return strings.TrimSpace(value)
	}
	return fallback
}

func envInt(name string, fallback int) (int, error) {
	raw := env(name, strconv.Itoa(fallback))
	value, err := strconv.Atoi(raw)
	if err != nil {
		return 0, fmt.Errorf("%s_INVALID", name)
	}
	return value, nil
}

func envBool(name string, fallback bool) (bool, error) {
	raw := env(name, strconv.FormatBool(fallback))
	value, err := strconv.ParseBool(raw)
	if err != nil {
		return false, fmt.Errorf("%s_INVALID", name)
	}
	return value, nil
}

func isPublicHTTPS(value string) bool {
	parsed, err := url.Parse(strings.TrimSpace(value))
	if err != nil || parsed.Scheme != "https" || parsed.Host == "" {
		return false
	}
	host := strings.ToLower(parsed.Hostname())
	return host != "localhost" && host != "127.0.0.1"
}
