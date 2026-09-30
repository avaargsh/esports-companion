package ordertimeout

import (
	"context"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/orders"
	"github.com/avaargsh/esports-companion/services/api-go/internal/workers/workerobs"
)

type Worker struct {
	repo                   orders.Repository
	redis                  *redis.Client
	logger                 *slog.Logger
	scanInterval           time.Duration
	finishConfirmTimeout   time.Duration
	assignmentStartTimeout time.Duration
	batchSize              int
	now                    func() time.Time
	observer               workerobs.CycleObserver
}

func New(
	db *pgxpool.Pool,
	redisClient *redis.Client,
	logger *slog.Logger,
	scanInterval time.Duration,
	finishConfirmTimeout time.Duration,
	assignmentStartTimeout time.Duration,
	batchSize int,
	observer workerobs.CycleObserver,
) *Worker {
	return &Worker{
		repo:                   orders.NewRepository(db),
		redis:                  redisClient,
		logger:                 logger,
		scanInterval:           scanInterval,
		finishConfirmTimeout:   finishConfirmTimeout,
		assignmentStartTimeout: assignmentStartTimeout,
		batchSize:              batchSize,
		now:                    time.Now,
		observer:               workerobs.OrNop(observer),
	}
}

func (w *Worker) Run(ctx context.Context) error {
	ticker := time.NewTicker(w.scanInterval)
	defer ticker.Stop()

	for {
		started := time.Now()
		processed, failures := w.scan(ctx)
		w.observer.ObserveCycle(
			"order-timeout",
			time.Since(started),
			processed,
			failures,
			nil,
		)

		select {
		case <-ctx.Done():
			return nil
		case <-ticker.C:
		}
	}
}

func (w *Worker) scan(ctx context.Context) (int, int) {
	effectiveNow := w.now().UTC()
	processed := 0
	failures := 0
	autoConfirmed := 0
	for autoConfirmed < w.batchSize {
		order, found, err := w.repo.AutoConfirmOneDue(
			ctx,
			effectiveNow,
			w.finishConfirmTimeout,
		)
		if err != nil {
			if ctx.Err() != nil {
				return
			}
			w.logger.Error(
				"order_timeout_auto_confirm_failed",
				"error", err,
			)
			failures++
			break
		}
		if !found {
			break
		}
		autoConfirmed++
		processed++
		w.logger.Info(
			"order_timeout_auto_confirmed",
			"order_id", order.ID,
		)
	}

	requeued := 0
	for requeued < w.batchSize {
		item, found, err := w.repo.RequeueOneTimedOutAssignment(
			ctx,
			effectiveNow,
			w.assignmentStartTimeout,
		)
		if err != nil {
			if ctx.Err() != nil {
				return
			}
			w.logger.Error(
				"order_timeout_assignment_requeue_failed",
				"error", err,
			)
			failures++
			break
		}
		if !found {
			break
		}
		requeued++
		processed++
		if err := w.redis.ZAdd(
			ctx,
			"order_pool:"+item.GameID,
			redis.Z{
				Score:  float64(item.CreatedAt.UnixNano()) / float64(time.Second),
				Member: item.OrderID,
			},
		).Err(); err != nil {
			w.logger.Error(
				"order_timeout_pool_rebuild_failed",
				"order_id", item.OrderID,
				"game_id", item.GameID,
				"error", err,
			)
			failures++
		}
		w.logger.Info(
			"order_timeout_assignment_requeued",
			"order_id", item.OrderID,
			"game_id", item.GameID,
		)
	}
	return processed, failures
}
