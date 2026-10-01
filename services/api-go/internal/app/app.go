package app

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	chimiddleware "github.com/go-chi/chi/v5/middleware"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"

	"github.com/avaargsh/esports-companion/services/api-go/internal/config"
	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/health"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/httpx"
	metricsx "github.com/avaargsh/esports-companion/services/api-go/internal/platform/metrics"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/postgresx"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/redisx"
)

type App struct {
	cfg    config.Config
	logger *slog.Logger
	server *http.Server
	pg     *pgxpool.Pool
	redis  *redis.Client
}

func New(ctx context.Context, cfg config.Config, logger *slog.Logger) (*App, error) {
	pg, err := postgresx.Open(ctx, cfg.DatabaseURL, cfg.DatabaseMinConns, cfg.DatabaseMaxConns)
	if err != nil {
		return nil, err
	}
	redisClient, err := redisx.Open(cfg.RedisURL, cfg.RedisPoolSize)
	if err != nil {
		pg.Close()
		return nil, err
	}

	registry := prometheus.NewRegistry()
	httpMetrics := metricsx.NewHTTP(registry)

	router := chi.NewRouter()
	router.Use(chimiddleware.RequestID)
	router.Use(chimiddleware.RealIP)
	router.Use(chimiddleware.Recoverer)
	router.Use(httpMetrics.Middleware)
	router.Use(httpx.AccessLog(logger))

	checker := health.Checker{
		Postgres: pg.Ping,
		Redis: func(ctx context.Context) error {
			return redisClient.Ping(ctx).Err()
		},
		RequireRedis: cfg.ReadinessRequireRedis,
	}

	router.Get("/livez", checker.Live)
	router.Get("/readyz", checker.Ready)
	router.Handle("/metrics", promhttp.HandlerFor(registry, promhttp.HandlerOpts{}))

	router.Route("/api/v1", func(r chi.Router) {
		r.Get("/runtime", func(w http.ResponseWriter, _ *http.Request) {
			payload, _ := json.Marshal(map[string]string{
				"service": cfg.ServiceName,
				"commit":  cfg.CommitSHA,
				"runtime": "go",
			})
			httpx.JSON(w, http.StatusOK, string(payload))
		})
	})

	server := &http.Server{
		Addr:              cfg.HTTPAddr,
		Handler:           router,
		ReadHeaderTimeout: 5 * time.Second,
		IdleTimeout:       60 * time.Second,
		// No global WriteTimeout: future SSE/WebSocket routes need streaming semantics.
	}

	return &App{
		cfg:    cfg,
		logger: logger,
		server: server,
		pg:     pg,
		redis:  redisClient,
	}, nil
}

func (a *App) Run(ctx context.Context) error {
	errCh := make(chan error, 1)
	go func() {
		a.logger.Info("api_go_listening",
			"addr", a.cfg.HTTPAddr,
			"service", a.cfg.ServiceName,
			"commit", a.cfg.CommitSHA,
		)
		errCh <- a.server.ListenAndServe()
	}()

	select {
	case err := <-errCh:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), a.cfg.ShutdownTimeout)
		defer cancel()
		if err := a.server.Shutdown(shutdownCtx); err != nil {
			return err
		}
		err := <-errCh
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	}
}

func (a *App) Close() {
	if a.redis != nil {
		_ = a.redis.Close()
	}
	if a.pg != nil {
		a.pg.Close()
	}
}
