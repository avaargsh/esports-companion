package metrics

import (
	"time"

	"github.com/prometheus/client_golang/prometheus"
)

type Worker struct {
	operationalScanSuccess *prometheus.GaugeVec
	outboxPending          prometheus.Gauge
	outboxOldestSeconds    prometheus.Gauge
	refundsInflight        prometheus.Gauge
	refundsOldestSeconds   prometheus.Gauge
	withdrawalsPending     prometheus.Gauge
	withdrawalsOldest      prometheus.Gauge
	disputesOpen           prometheus.Gauge
	disputesOldest         prometheus.Gauge
	finishPending          prometheus.Gauge
	finishOverdue          prometheus.Gauge
	finishOldest           prometheus.Gauge
	assignmentOverdue      prometheus.Gauge
	refundReconcileDue     prometheus.Gauge
	cycles                 *prometheus.CounterVec
	cycleDuration          *prometheus.HistogramVec
	items                  *prometheus.CounterVec
	lastSuccess            *prometheus.GaugeVec
}

func NewWorker(reg prometheus.Registerer) *Worker {
	m := &Worker{
		operationalScanSuccess: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "esports_operational_metrics_scan_success",
				Help: "Whether the latest PostgreSQL operational metrics scan succeeded.",
			},
			[]string{"source"},
		),
		outboxPending: prometheus.NewGauge(
			prometheus.GaugeOpts{
				Name: "esports_outbox_pending",
				Help: "Pending transactional outbox events.",
			},
		),
		outboxOldestSeconds: prometheus.NewGauge(
			prometheus.GaugeOpts{
				Name: "esports_outbox_oldest_pending_seconds",
				Help: "Age in seconds of the oldest pending outbox event.",
			},
		),
		refundsInflight: prometheus.NewGauge(
			prometheus.GaugeOpts{
				Name: "esports_refunds_inflight",
				Help: "Refunds waiting for provider completion or reconciliation.",
			},
		),
		refundsOldestSeconds: prometheus.NewGauge(
			prometheus.GaugeOpts{
				Name: "esports_refunds_oldest_inflight_seconds",
				Help: "Age in seconds of the oldest in-flight refund.",
			},
		),
		withdrawalsPending: prometheus.NewGauge(
			prometheus.GaugeOpts{
				Name: "esports_withdrawals_pending",
				Help: "Withdrawals waiting for completion or rejection.",
			},
		),
		withdrawalsOldest: prometheus.NewGauge(
			prometheus.GaugeOpts{
				Name: "esports_withdrawals_oldest_pending_seconds",
				Help: "Age in seconds of the oldest pending withdrawal.",
			},
		),
		disputesOpen: prometheus.NewGauge(
			prometheus.GaugeOpts{
				Name: "esports_disputes_open",
				Help: "Open or resolving disputes.",
			},
		),
		disputesOldest: prometheus.NewGauge(
			prometheus.GaugeOpts{
				Name: "esports_disputes_oldest_open_seconds",
				Help: "Age in seconds of the oldest open or resolving dispute.",
			},
		),
		finishPending: prometheus.NewGauge(
			prometheus.GaugeOpts{
				Name: "esports_finish_requests_pending",
				Help: "Orders waiting for customer completion confirmation.",
			},
		),
		finishOverdue: prometheus.NewGauge(
			prometheus.GaugeOpts{
				Name: "esports_finish_requests_overdue",
				Help: "Finish requests older than auto-confirm timeout plus scan grace.",
			},
		),
		finishOldest: prometheus.NewGauge(
			prometheus.GaugeOpts{
				Name: "esports_finish_requests_oldest_seconds",
				Help: "Age in seconds of the oldest pending finish request.",
			},
		),
		assignmentOverdue: prometheus.NewGauge(
			prometheus.GaugeOpts{
				Name: "esports_assignments_start_overdue",
				Help: "Accepted orders whose provider start timeout has elapsed.",
			},
		),
		refundReconcileDue: prometheus.NewGauge(
			prometheus.GaugeOpts{
				Name: "esports_refunds_reconcile_due",
				Help: "WeChat refunds currently eligible for reconciliation.",
			},
		),
		cycles: prometheus.NewCounterVec(
			prometheus.CounterOpts{
				Name: "esports_worker_cycles_total",
				Help: "Background worker cycles by worker and result.",
			},
			[]string{"worker", "result"},
		),
		cycleDuration: prometheus.NewHistogramVec(
			prometheus.HistogramOpts{
				Name:    "esports_worker_cycle_duration_seconds",
				Help:    "Background worker cycle duration.",
				Buckets: prometheus.DefBuckets,
			},
			[]string{"worker"},
		),
		items: prometheus.NewCounterVec(
			prometheus.CounterOpts{
				Name: "esports_worker_items_total",
				Help: "Background worker items by worker and outcome.",
			},
			[]string{"worker", "outcome"},
		),
		lastSuccess: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "esports_worker_last_success_unixtime",
				Help: "Unix timestamp of the latest fully successful worker cycle.",
			},
			[]string{"worker"},
		),
	}
	reg.MustRegister(
		m.operationalScanSuccess,
		m.outboxPending,
		m.outboxOldestSeconds,
		m.refundsInflight,
		m.refundsOldestSeconds,
		m.withdrawalsPending,
		m.withdrawalsOldest,
		m.disputesOpen,
		m.disputesOldest,
		m.finishPending,
		m.finishOverdue,
		m.finishOldest,
		m.assignmentOverdue,
		m.refundReconcileDue,
		m.cycles,
		m.cycleDuration,
		m.items,
		m.lastSuccess,
	)
	return m
}

func (m *Worker) ObserveCycle(
	worker string,
	duration time.Duration,
	processed int,
	failures int,
	err error,
) {
	result := "success"
	if err != nil {
		result = "failure"
	} else if failures > 0 {
		result = "partial"
	}
	m.cycles.WithLabelValues(worker, result).Inc()
	m.cycleDuration.WithLabelValues(worker).Observe(duration.Seconds())
	if processed > 0 {
		m.items.WithLabelValues(worker, "success").Add(float64(processed))
	}
	if failures > 0 {
		m.items.WithLabelValues(worker, "failure").Add(float64(failures))
	}
	if result == "success" {
		m.lastSuccess.WithLabelValues(worker).SetToCurrentTime()
	}
}
