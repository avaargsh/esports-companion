package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"github.com/avaargsh/esports-companion/services/api-go/internal/config"
	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/refunds"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/postgresx"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/redisx"
	"github.com/avaargsh/esports-companion/services/api-go/internal/workers/ordertimeout"
	"github.com/avaargsh/esports-companion/services/api-go/internal/workers/outbox"
	"github.com/avaargsh/esports-companion/services/api-go/internal/workers/refundreconcile"
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
	timeoutWorker := ordertimeout.New(
		pg,
		redisClient,
		logger,
		cfg.OrderTimeoutScanInterval,
		cfg.FinishConfirmTimeout,
		cfg.AssignmentStartTimeout,
		cfg.OrderTimeoutBatchSize,
	)

	refundProvider, err := refunds.ProviderFromConfig(cfg)
	if err != nil {
		logger.Error("refund provider bootstrap failed", "error", err)
		os.Exit(1)
	}
	refundWorker := refundreconcile.New(
		pg,
		refunds.NewService(refunds.NewRepository(pg), refundProvider),
		logger,
		refundreconcile.Enabled(cfg.RefundProvider),
		cfg.RefundReconcileScanInterval,
		cfg.RefundReconcileMinAge,
		cfg.RefundReconcileBatchSize,
	)

	logger.Info(
		"background_workers_started",
		"outbox_poll_interval", cfg.OutboxPollInterval.String(),
		"outbox_batch_size", cfg.OutboxBatchSize,
		"order_timeout_scan_interval", cfg.OrderTimeoutScanInterval.String(),
		"order_timeout_batch_size", cfg.OrderTimeoutBatchSize,
		"refund_reconcile_enabled", refundreconcile.Enabled(cfg.RefundProvider),
		"refund_reconcile_scan_interval", cfg.RefundReconcileScanInterval.String(),
		"refund_reconcile_batch_size", cfg.RefundReconcileBatchSize,
	)

	type workerResult struct {
		name string
		err  error
	}
	runCtx, cancel := context.WithCancel(ctx)
	defer cancel()
	results := make(chan workerResult, 3)
	go func() {
		results <- workerResult{name: "outbox", err: publisher.Run(runCtx)}
	}()
	go func() {
		results <- workerResult{name: "order-timeout", err: timeoutWorker.Run(runCtx)}
	}()
	go func() {
		results <- workerResult{name: "refund-reconcile", err: refundWorker.Run(runCtx)}
	}()

	select {
	case <-ctx.Done():
		cancel()
		for range 3 {
			<-results
		}
		logger.Info("background_workers_stopped")
	case result := <-results:
		cancel()
		remaining := []workerResult{result}
		for range 2 {
			remaining = append(remaining, <-results)
		}
		for _, item := range remaining {
			if item.err != nil {
				logger.Error(
					"background_worker_stopped_with_error",
					"worker", item.name,
					"error", item.err,
				)
			} else if item.name == result.name && ctx.Err() == nil {
				logger.Error(
					"background_worker_stopped_unexpectedly",
					"worker", item.name,
				)
			}
		}
		if ctx.Err() == nil {
			os.Exit(1)
		}
	}
}
