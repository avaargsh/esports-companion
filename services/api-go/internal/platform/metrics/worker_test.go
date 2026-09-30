package metrics

import (
	"errors"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgtype"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/testutil"
)

func TestWorkerCycleMetrics(t *testing.T) {
	registry := prometheus.NewRegistry()
	metrics := NewWorker(registry)

	metrics.ObserveCycle(
		"outbox",
		250*time.Millisecond,
		3,
		0,
		nil,
	)
	metrics.ObserveCycle(
		"outbox",
		100*time.Millisecond,
		1,
		2,
		nil,
	)
	metrics.ObserveCycle(
		"outbox",
		50*time.Millisecond,
		0,
		1,
		errors.New("boom"),
	)

	if got := testutil.ToFloat64(
		metrics.cycles.WithLabelValues("outbox", "success"),
	); got != 1 {
		t.Fatalf("success cycles = %v", got)
	}
	if got := testutil.ToFloat64(
		metrics.cycles.WithLabelValues("outbox", "partial"),
	); got != 1 {
		t.Fatalf("partial cycles = %v", got)
	}
	if got := testutil.ToFloat64(
		metrics.cycles.WithLabelValues("outbox", "failure"),
	); got != 1 {
		t.Fatalf("failure cycles = %v", got)
	}
	if got := testutil.ToFloat64(
		metrics.items.WithLabelValues("outbox", "success"),
	); got != 4 {
		t.Fatalf("successful items = %v", got)
	}
	if got := testutil.ToFloat64(
		metrics.items.WithLabelValues("outbox", "failure"),
	); got != 3 {
		t.Fatalf("failed items = %v", got)
	}
	if got := testutil.ToFloat64(
		metrics.lastSuccess.WithLabelValues("outbox"),
	); got <= 0 {
		t.Fatalf("last success = %v", got)
	}
}

func TestAgeSecondsClampsFutureTimestamp(t *testing.T) {
	now := time.Date(2026, 10, 1, 0, 0, 0, 0, time.UTC)
	oldest := pgTimestamp(now.Add(time.Minute))
	if got := ageSeconds(now, oldest); got != 0 {
		t.Fatalf("age = %v", got)
	}
}

func pgTimestamp(value time.Time) pgtype.Timestamptz {
	return pgtype.Timestamptz{
		Time:  value,
		Valid: true,
	}
}
