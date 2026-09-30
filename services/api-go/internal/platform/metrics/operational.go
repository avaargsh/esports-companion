package metrics

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"
)

type OperationalScanner struct {
	db                     *pgxpool.Pool
	metrics                *Worker
	logger                 *slog.Logger
	scanInterval           time.Duration
	finishConfirmTimeout   time.Duration
	orderTimeoutScanGrace  time.Duration
	assignmentStartTimeout time.Duration
	refundReconcileMinAge  time.Duration
	now                    func() time.Time
}

func NewOperationalScanner(
	db *pgxpool.Pool,
	metrics *Worker,
	logger *slog.Logger,
	scanInterval time.Duration,
	finishConfirmTimeout time.Duration,
	orderTimeoutScanGrace time.Duration,
	assignmentStartTimeout time.Duration,
	refundReconcileMinAge time.Duration,
) *OperationalScanner {
	return &OperationalScanner{
		db:                     db,
		metrics:                metrics,
		logger:                 logger,
		scanInterval:           scanInterval,
		finishConfirmTimeout:   finishConfirmTimeout,
		orderTimeoutScanGrace:  orderTimeoutScanGrace,
		assignmentStartTimeout: assignmentStartTimeout,
		refundReconcileMinAge:  refundReconcileMinAge,
		now:                    time.Now,
	}
}

func (s *OperationalScanner) Run(ctx context.Context) error {
	ticker := time.NewTicker(s.scanInterval)
	defer ticker.Stop()

	for {
		started := time.Now()
		err := s.Refresh(ctx, s.now().UTC())
		s.metrics.ObserveCycle(
			"operational-metrics",
			time.Since(started),
			boolCount(err == nil),
			boolCount(err != nil),
			err,
		)
		if err != nil && ctx.Err() == nil {
			s.logger.Error("operational_metrics_scan_failed", "error", err)
		}

		select {
		case <-ctx.Done():
			return nil
		case <-ticker.C:
		}
	}
}

func (s *OperationalScanner) Refresh(ctx context.Context, now time.Time) error {
	if err := s.refreshOutbox(ctx, now); err != nil {
		s.metrics.operationalScanSuccess.WithLabelValues("postgres").Set(0)
		return err
	}
	if err := s.refreshRefunds(ctx, now); err != nil {
		s.metrics.operationalScanSuccess.WithLabelValues("postgres").Set(0)
		return err
	}
	if err := s.refreshWithdrawals(ctx, now); err != nil {
		s.metrics.operationalScanSuccess.WithLabelValues("postgres").Set(0)
		return err
	}
	if err := s.refreshDisputes(ctx, now); err != nil {
		s.metrics.operationalScanSuccess.WithLabelValues("postgres").Set(0)
		return err
	}
	if err := s.refreshFinishRequests(ctx, now); err != nil {
		s.metrics.operationalScanSuccess.WithLabelValues("postgres").Set(0)
		return err
	}
	if err := s.refreshAssignmentTimeouts(ctx, now); err != nil {
		s.metrics.operationalScanSuccess.WithLabelValues("postgres").Set(0)
		return err
	}
	s.metrics.operationalScanSuccess.WithLabelValues("postgres").Set(1)
	return nil
}

func (s *OperationalScanner) refreshOutbox(ctx context.Context, now time.Time) error {
	count, oldest, err := countAndOldest(
		ctx,
		s.db,
		`SELECT count(*), min(created_at)
		   FROM outbox_events
		  WHERE status = 'PENDING'`,
	)
	if err != nil {
		return fmt.Errorf("scan outbox metrics: %w", err)
	}
	s.metrics.outboxPending.Set(float64(count))
	s.metrics.outboxOldestSeconds.Set(ageSeconds(now, oldest))
	return nil
}

func (s *OperationalScanner) refreshRefunds(ctx context.Context, now time.Time) error {
	count, oldest, err := countAndOldest(
		ctx,
		s.db,
		`SELECT count(*), min(updated_at)
		   FROM refunds
		  WHERE status IN ('PENDING', 'SUBMITTING', 'PROCESSING')`,
	)
	if err != nil {
		return fmt.Errorf("scan refund metrics: %w", err)
	}
	s.metrics.refundsInflight.Set(float64(count))
	s.metrics.refundsOldestSeconds.Set(ageSeconds(now, oldest))

	cutoff := now.Add(-s.refundReconcileMinAge)
	var due int64
	if err := s.db.QueryRow(ctx, `
		SELECT count(*)
		FROM refunds
		WHERE provider = 'WECHAT'
		  AND status IN ('SUBMITTING', 'PROCESSING')
		  AND out_refund_no IS NOT NULL
		  AND updated_at <= $1
	`, cutoff).Scan(&due); err != nil {
		return fmt.Errorf("scan due refund metrics: %w", err)
	}
	s.metrics.refundReconcileDue.Set(float64(due))
	return nil
}

func (s *OperationalScanner) refreshWithdrawals(ctx context.Context, now time.Time) error {
	count, oldest, err := countAndOldest(
		ctx,
		s.db,
		`SELECT count(*), min(created_at)
		   FROM withdrawals
		  WHERE status = 'PENDING'`,
	)
	if err != nil {
		return fmt.Errorf("scan withdrawal metrics: %w", err)
	}
	s.metrics.withdrawalsPending.Set(float64(count))
	s.metrics.withdrawalsOldest.Set(ageSeconds(now, oldest))
	return nil
}

func (s *OperationalScanner) refreshDisputes(ctx context.Context, now time.Time) error {
	count, oldest, err := countAndOldest(
		ctx,
		s.db,
		`SELECT count(*), min(created_at)
		   FROM disputes
		  WHERE status IN ('OPEN', 'RESOLVING')`,
	)
	if err != nil {
		return fmt.Errorf("scan dispute metrics: %w", err)
	}
	s.metrics.disputesOpen.Set(float64(count))
	s.metrics.disputesOldest.Set(ageSeconds(now, oldest))
	return nil
}

func (s *OperationalScanner) refreshFinishRequests(ctx context.Context, now time.Time) error {
	count, oldest, err := countAndOldest(
		ctx,
		s.db,
		`SELECT count(*), min(finish_requested_at)
		   FROM orders
		  WHERE status = 'FINISH_REQUESTED'`,
	)
	if err != nil {
		return fmt.Errorf("scan finish request metrics: %w", err)
	}
	s.metrics.finishPending.Set(float64(count))
	s.metrics.finishOldest.Set(ageSeconds(now, oldest))

	deadline := now.Add(-(s.finishConfirmTimeout + s.orderTimeoutScanGrace))
	var overdue int64
	if err := s.db.QueryRow(ctx, `
		SELECT count(*)
		FROM orders
		WHERE status = 'FINISH_REQUESTED'
		  AND finish_requested_at IS NOT NULL
		  AND finish_requested_at < $1
	`, deadline).Scan(&overdue); err != nil {
		return fmt.Errorf("scan overdue finish requests: %w", err)
	}
	s.metrics.finishOverdue.Set(float64(overdue))
	return nil
}

func (s *OperationalScanner) refreshAssignmentTimeouts(ctx context.Context, now time.Time) error {
	cutoff := now.Add(-s.assignmentStartTimeout)
	var overdue int64
	if err := s.db.QueryRow(ctx, `
		SELECT count(*)
		FROM orders
		WHERE status = 'ACCEPTED'
		  AND accepted_at IS NOT NULL
		  AND accepted_at <= $1
	`, cutoff).Scan(&overdue); err != nil {
		return fmt.Errorf("scan overdue assignments: %w", err)
	}
	s.metrics.assignmentOverdue.Set(float64(overdue))
	return nil
}

func countAndOldest(
	ctx context.Context,
	db *pgxpool.Pool,
	query string,
) (int64, pgtype.Timestamptz, error) {
	var (
		count  int64
		oldest pgtype.Timestamptz
	)
	if err := db.QueryRow(ctx, query).Scan(&count, &oldest); err != nil {
		return 0, pgtype.Timestamptz{}, err
	}
	return count, oldest, nil
}

func ageSeconds(now time.Time, oldest pgtype.Timestamptz) float64 {
	if !oldest.Valid {
		return 0
	}
	value := now.Sub(oldest.Time.UTC()).Seconds()
	if value < 0 {
		return 0
	}
	return value
}

func boolCount(value bool) int {
	if value {
		return 1
	}
	return 0
}
