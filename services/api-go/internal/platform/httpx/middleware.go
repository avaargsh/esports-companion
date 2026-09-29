package httpx

import (
	"encoding/json"
	"log/slog"
	"net/http"
	"regexp"
	"time"

	chimiddleware "github.com/go-chi/chi/v5/middleware"
)

var uuidPattern = regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`)

func AccessLog(logger *slog.Logger) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			started := time.Now()
			ww := chimiddleware.NewWrapResponseWriter(w, r.ProtoMajor)
			next.ServeHTTP(ww, r)

			logger.Info("http_request",
				"request_id", chimiddleware.GetReqID(r.Context()),
				"method", r.Method,
				"path", r.URL.Path,
				"status", ww.Status(),
				"bytes", ww.BytesWritten(),
				"duration_ms", time.Since(started).Milliseconds(),
			)
		})
	}
}

func JSON(w http.ResponseWriter, status int, body string) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_, _ = w.Write([]byte(body))
}

func JSONValue(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(value); err != nil {
		slog.Error("encode response failed", "error", err)
	}
}

func Error(w http.ResponseWriter, status int, detail string) {
	JSONValue(w, status, map[string]string{"detail": detail})
}

func ValidationError(w http.ResponseWriter, location, field, message string) {
	JSONValue(w, http.StatusUnprocessableEntity, map[string]any{
		"detail": []map[string]any{
			{
				"type": "value_error",
				"loc":  []string{location, field},
				"msg":  message,
			},
		},
	})
}

func IsUUID(value string) bool {
	return uuidPattern.MatchString(value)
}
