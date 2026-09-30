package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"github.com/avaargsh/esports-companion/services/api-go/internal/config"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/postgresx"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/redisx"
	"github.com/avaargsh/esports-companion/services/api-go/internal/workers/outbox"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		slog.Error("configuration rejected", "error", err)
		os.Exit(2)
	}

	level := slog.LevelInfo
	if cfg.LogLevel == "DEBUG" {
		level = slog.LevelDebug
	}
	logger := slog.New(
		slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: level}),
	)
	slog.SetDefault(logger)

	ctx, stop := signal.NotifyContext(
		context.Background(),
		syscall.SIGINT,
		syscall.SIGTERM,
	)
	defer stop()

	pg, err := postgresx.Open(
		ctx,
		cfg.DatabaseURL,
		cfg.DatabaseMinConns,
		cfg.DatabaseMaxConns,
	)
	if err != nil {
		logger.Error("worker postgres bootstrap failed", "error", err)
		os.Exit(1)
	}
	defer pg.Close()
	if err := pg.Ping(ctx); err != nil {
		logger.Error("worker postgres readiness failed", "error", err)
		os.Exit(1)
	}

	redisClient, err := redisx.Open(cfg.RedisURL, cfg.RedisPoolSize)
	if err != nil {
		logger.Error("worker redis bootstrap failed", "error", err)
		os.Exit(1)
	}
	defer func() { _ = redisClient.Close() }()
	if err := redisClient.Ping(ctx).Err(); err != nil {
		logger.Error("worker redis readiness failed", "error", err)
		os.Exit(1)
	}

	publisher := outbox.New(
		pg,
		redisClient,
		logger,
		cfg.OutboxPollInterval,
		cfg.OutboxBatchSize,
	)
	logger.Info(
		"background_worker_started",
		"worker", "outbox",
		"poll_interval", cfg.OutboxPollInterval.String(),
		"batch_size", cfg.OutboxBatchSize,
	)
	if err := publisher.Run(ctx); err != nil {
		logger.Error("background worker stopped with error", "error", err)
		os.Exit(1)
	}
	logger.Info("background_worker_stopped", "worker", "outbox")
}
