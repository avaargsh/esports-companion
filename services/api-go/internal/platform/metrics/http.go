package metrics

import (
	"net/http"
	"strconv"
	"time"

	"github.com/go-chi/chi/v5"
	chimiddleware "github.com/go-chi/chi/v5/middleware"
	"github.com/prometheus/client_golang/prometheus"
)

var httpDurationBuckets = []float64{
	0.005,
	0.01,
	0.025,
	0.05,
	0.1,
	0.25,
	0.5,
	1.0,
	2.5,
	5.0,
}

type HTTP struct {
	requests *prometheus.CounterVec
	duration *prometheus.HistogramVec
	inflight *prometheus.GaugeVec
}

func NewHTTP(reg prometheus.Registerer) *HTTP {
	m := &HTTP{
		requests: prometheus.NewCounterVec(
			prometheus.CounterOpts{
				Name: "esports_http_requests_total",
				Help: "HTTP requests completed by the API.",
			},
			[]string{"method", "route", "status"},
		),
		duration: prometheus.NewHistogramVec(
			prometheus.HistogramOpts{
				Name:    "esports_http_request_duration_seconds",
				Help:    "HTTP request latency by stable route template.",
				Buckets: httpDurationBuckets,
			},
			[]string{"method", "route"},
		),
		inflight: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "esports_http_inflight_requests",
				Help: "HTTP requests currently executing.",
			},
			[]string{"method"},
		),
	}
	reg.MustRegister(m.requests, m.duration, m.inflight)
	return m
}

func (m *HTTP) Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		started := time.Now()
		m.inflight.WithLabelValues(r.Method).Inc()
		defer m.inflight.WithLabelValues(r.Method).Dec()

		ww := chimiddleware.NewWrapResponseWriter(w, r.ProtoMajor)
		next.ServeHTTP(ww, r)

		route := chi.RouteContext(r.Context()).RoutePattern()
		if route == "" {
			route = "unmatched"
		}
		if route == "/metrics" {
			return
		}
		m.requests.WithLabelValues(
			r.Method,
			route,
			strconv.Itoa(ww.Status()),
		).Inc()
		m.duration.WithLabelValues(
			r.Method,
			route,
		).Observe(time.Since(started).Seconds())
	})
}
