package health

import (
	"context"
	"net/http"
	"time"

	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/httpx"
)

type Checker struct {
	Postgres     func(context.Context) error
	Redis        func(context.Context) error
	RequireRedis bool
}

func (c Checker) Live(w http.ResponseWriter, _ *http.Request) {
	httpx.JSONValue(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (c Checker) Ready(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()

	if err := c.Postgres(ctx); err != nil {
		httpx.JSONValue(w, http.StatusServiceUnavailable, map[string]string{
			"status":     "not_ready",
			"dependency": "postgres",
		})
		return
	}
	if c.RequireRedis {
		if err := c.Redis(ctx); err != nil {
			httpx.JSONValue(w, http.StatusServiceUnavailable, map[string]string{
				"status":     "not_ready",
				"dependency": "redis",
			})
			return
		}
	}
	httpx.JSONValue(w, http.StatusOK, map[string]string{"status": "ready"})
}
