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
	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/auth"
	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/catalog"
	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/health"
	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/marketplace"
	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/offerings"
	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/orders"
	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/payments"
	realtimex "github.com/avaargsh/esports-companion/services/api-go/internal/modules/realtime"
	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/refunds"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/httpx"
	metricsx "github.com/avaargsh/esports-companion/services/api-go/internal/platform/metrics"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/postgresx"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/redisx"
)

type App struct {
	cfg      config.Config
	logger   *slog.Logger
	server   *http.Server
	pg       *pgxpool.Pool
	redis    *redis.Client
	realtime *realtimex.Hub
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

	authProvider := auth.NewProvider(cfg)
	authService := auth.NewService(auth.NewRepository(pg), authProvider, cfg)
	authHandler := auth.NewHandler(authService, cfg.IsSecureDeployment())
	catalogHandler := catalog.NewHandler(catalog.NewRepository(pg))
	marketplaceHandler := marketplace.NewHandler(marketplace.NewRepository(pg))
	offeringsHandler := offerings.NewHandler(
		offerings.NewRepository(pg),
		authService,
		cfg.IsSecureDeployment(),
	)
	orderRepository := orders.NewRepository(pg)
	ordersHandler := orders.NewHandler(
		orders.NewService(orderRepository),
		authService,
		cfg.IsSecureDeployment(),
	)
	paymentProvider, err := payments.ProviderFromConfig(cfg)
	if err != nil {
		_ = redisClient.Close()
		pg.Close()
		return nil, err
	}
	callbackVerifier, callbackErr := payments.NewWeChatCallbackVerifier(cfg)
	if callbackErr != nil && cfg.IsSecureDeployment() {
		_ = redisClient.Close()
		pg.Close()
		return nil, callbackErr
	}
	if callbackErr != nil {
		callbackVerifier = nil
	}
	paymentsHandler := payments.NewHandler(
		payments.NewService(payments.NewRepository(pg), paymentProvider),
		authService,
		callbackVerifier,
		cfg.IsSecureDeployment(),
	)

	refundProvider, err := refunds.ProviderFromConfig(cfg)
	if err != nil {
		_ = redisClient.Close()
		pg.Close()
		return nil, err
	}
	refundCallbackVerifier, refundCallbackErr := refunds.NewWeChatRefundCallbackVerifier(cfg)
	if refundCallbackErr != nil && cfg.IsSecureDeployment() {
		_ = redisClient.Close()
		pg.Close()
		return nil, refundCallbackErr
	}
	if refundCallbackErr != nil {
		refundCallbackVerifier = nil
	}
	refundsHandler := refunds.NewHandler(
		refunds.NewService(refunds.NewRepository(pg), refundProvider),
		authService,
		refundCallbackVerifier,
		cfg.IsSecureDeployment(),
	)

	realtimeRepository := realtimex.NewRepository(pg)
	realtimeHub := realtimex.NewHub(
		realtimeRepository,
		redisClient,
		logger,
	)
	realtimeHandler := realtimex.NewHandler(
		ctx,
		authService,
		realtimeRepository,
		realtimeHub,
		cfg.IsSecureDeployment(),
	)

	realtimeHandler.Register(router)

	router.Route("/api/v1", func(r chi.Router) {
		r.Get("/runtime", func(w http.ResponseWriter, _ *http.Request) {
			payload, _ := json.Marshal(map[string]string{
				"service": cfg.ServiceName,
				"commit":  cfg.CommitSHA,
				"runtime": "go",
			})
			httpx.JSON(w, http.StatusOK, string(payload))
		})
		authHandler.Register(r)
		catalogHandler.Register(r)
		marketplaceHandler.Register(r)
		offeringsHandler.Register(r)
		ordersHandler.Register(r)
		paymentsHandler.Register(r)
		refundsHandler.Register(r)
	})

	server := &http.Server{
		Addr:              cfg.HTTPAddr,
		Handler:           router,
		ReadHeaderTimeout: 5 * time.Second,
		IdleTimeout:       60 * time.Second,
		// No global WriteTimeout: future SSE/WebSocket routes need streaming semantics.
	}

	return &App{
		cfg:      cfg,
		logger:   logger,
		server:   server,
		pg:       pg,
		redis:    redisClient,
		realtime: realtimeHub,
	}, nil
}

func (a *App) Run(ctx context.Context) error {
	runCtx, cancel := context.WithCancel(ctx)
	defer cancel()
	go a.realtime.Run(runCtx)

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
