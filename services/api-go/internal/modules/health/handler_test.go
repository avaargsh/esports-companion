package health

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestReadyReportsOnlyCheckedDependencies(t *testing.T) {
	for _, requireRedis := range []bool{false, true} {
		redisChecked := false
		c := Checker{
			Postgres: func(context.Context) error { return nil },
			Redis: func(context.Context) error {
				redisChecked = true
				return nil
			},
			RequireRedis: requireRedis,
		}
		response := httptest.NewRecorder()
		c.Ready(response, httptest.NewRequest(http.MethodGet, "/readyz", nil))
		var body struct {
			Status       string          `json:"status"`
			Dependencies map[string]bool `json:"dependencies"`
		}
		if err := json.Unmarshal(response.Body.Bytes(), &body); err != nil {
			t.Fatal(err)
		}
		if response.Code != http.StatusOK || body.Status != "ready" || !body.Dependencies["postgres"] {
			t.Fatalf("unexpected readiness: %d %s", response.Code, response.Body)
		}
		if redisOK, reported := body.Dependencies["redis"]; redisChecked != requireRedis || reported != requireRedis || redisOK != requireRedis {
			t.Fatalf("Redis requirement=%v, checked=%v, reported=%v, ok=%v", requireRedis, redisChecked, reported, redisOK)
		}
	}
}

func TestReadyKeepsRequiredRedisFailure(t *testing.T) {
	c := Checker{
		Postgres:     func(context.Context) error { return nil },
		Redis:        func(context.Context) error { return errors.New("unavailable") },
		RequireRedis: true,
	}
	response := httptest.NewRecorder()
	c.Ready(response, httptest.NewRequest(http.MethodGet, "/readyz", nil))
	if response.Code != http.StatusServiceUnavailable || response.Body.String() != `{"status":"not_ready","dependency":"redis"}` {
		t.Fatalf("unexpected failure: %d %s", response.Code, response.Body)
	}
}
