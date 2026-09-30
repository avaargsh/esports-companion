package refundreconcile

import (
	"context"
	"log/slog"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/refunds"
	"github.com/avaargsh/esports-companion/services/api-go/internal/workers/workerobs"
)

type Worker struct {
	db           *pgxpool.Pool
	service      refunds.Service
	logger       *slog.Logger
	enabled      bool
	scanInterval time.Duration
	minAge       time.Duration
	batchSize    int
	observer     workerobs.CycleObserver
}

func New(
	db *pgxpool.Pool,
	service refunds.Service,
	logger *slog.Logger,
	enabled bool,
	scanInterval time.Duration,
	minAge time.Duration,
	batchSize int,
	observer workerobs.CycleObserver,
) *Worker {
	return &Worker{
		db:           db,
		service:      service,
		logger:       logger,
		enabled:      enabled,
		scanInterval: scanInterval,
		minAge:       minAge,
		batchSize:    batchSize,
		observer:     workerobs.OrNop(observer),
	}
}

func (w *Worker) Run(ctx context.Context) error {
	if !w.enabled {
		w.logger.Info("refund_reconcile_worker_disabled")
		<-ctx.Done()
		return nil
	}

	w.runScan(ctx)
	ticker := time.NewTicker(w.scanInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return nil
		case <-ticker.C:
			w.runScan(ctx)
		}
	}
}

func (w *Worker) runScan(ctx context.Context) {
	started := time.Now()
	processed, failures, err := w.scan(ctx)
	w.observer.ObserveCycle(
		"refund-reconcile",
		time.Since(started),
		processed,
		failures,
		err,
	)
	if err != nil && ctx.Err() == nil {
		w.logger.Error("refund_reconcile_scan_failed", "error", err)
	}
}

func (w *Worker) scan(ctx context.Context) (int, int, error) {
	ids, err := w.candidateIDs(ctx, time.Now().UTC())
	if err != nil {
		return 0, 0, err
	}
	processed := 0
	failures := 0
	for _, refundID := range ids {
		if ctx.Err() != nil {
			return processed, failures, nil
		}
		claimed, err := w.reconcileOne(ctx, refundID)
		if err != nil {
			w.logger.Error(
				"refund_reconcile_failed",
				"refund_id", refundID,
				"error", err,
			)
			if claimed {
				failures++
			}
			continue
		}
		if claimed {
			processed++
			w.logger.Info("refund_reconciled", "refund_id", refundID)
		}
	}
	return processed, failures, nil
}

func (w *Worker) candidateIDs(ctx context.Context, now time.Time) ([]string, error) {
	cutoff := now.Add(-w.minAge)
	rows, err := w.db.Query(ctx, `
		SELECT id::text
		FROM refunds
		WHERE provider = 'WECHAT'
		  AND status IN ('SUBMITTING', 'PROCESSING')
		  AND out_refund_no IS NOT NULL
		  AND updated_at <= $1
		ORDER BY updated_at, id
		LIMIT $2
	`, cutoff, w.batchSize)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	ids := make([]string, 0, w.batchSize)
	for rows.Next() {
		var refundID string
		if err := rows.Scan(&refundID); err != nil {
			return nil, err
		}
		ids = append(ids, refundID)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return ids, nil
}

func (w *Worker) reconcileOne(ctx context.Context, refundID string) (bool, error) {
	conn, err := w.db.Acquire(ctx)
	if err != nil {
		return false, err
	}
	defer conn.Release()

	const lockSQL = `SELECT pg_try_advisory_lock(hashtextextended($1, 0))`
	var claimed bool
	if err := conn.QueryRow(ctx, lockSQL, refundID).Scan(&claimed); err != nil {
		return false, err
	}
	if !claimed {
		return false, nil
	}
	defer func() {
		unlockCtx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		var unlocked bool
		if err := conn.QueryRow(
			unlockCtx,
			`SELECT pg_advisory_unlock(hashtextextended($1, 0))`,
			refundID,
		).Scan(&unlocked); err != nil {
			w.logger.Error(
				"refund_reconcile_unlock_failed",
				"refund_id", refundID,
				"error", err,
			)
		} else if !unlocked {
			w.logger.Warn(
				"refund_reconcile_unlock_not_held",
				"refund_id", refundID,
			)
		}
	}()

	_, err = w.service.Reconcile(ctx, refundID)
	if err != nil {
		// Provider/query and aggregate validation errors are isolated to one
		// refund. The next scan may retry transient provider failures.
		return true, err
	}
	return true, nil
}

func Enabled(providerName string) bool {
	return strings.EqualFold(strings.TrimSpace(providerName), "wechat")
}
