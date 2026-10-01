package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"github.com/avaargsh/esports-companion/services/api-go/internal/app"
	"github.com/avaargsh/esports-companion/services/api-go/internal/config"
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
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: level}))
	slog.SetDefault(logger)

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	application, err := app.New(ctx, cfg, logger)
	if err != nil {
		logger.Error("application bootstrap failed", "error", err)
		os.Exit(1)
	}
	defer application.Close()

	if err := application.Run(ctx); err != nil {
		logger.Error("server stopped with error", "error", err)
		os.Exit(1)
	}
}
