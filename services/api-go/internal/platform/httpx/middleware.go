package httpx

import (
	"encoding/json"
	"log/slog"
	"net/http"
	"strings"
	"time"

	chimiddleware "github.com/go-chi/chi/v5/middleware"
)

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

// IsUUID mirrors the textual UUID forms accepted by the FastAPI/Pydantic
// contract closely enough for route/query compatibility. It deliberately does
// not restrict the UUID version.
func IsUUID(value string) bool {
	s := value
	const urnPrefix = "urn:uuid:"
	if len(s) >= len(urnPrefix) && strings.EqualFold(s[:len(urnPrefix)], urnPrefix) {
		s = s[len(urnPrefix):]
	}
	if len(s) == 38 && s[0] == '{' && s[len(s)-1] == '}' {
		s = s[1 : len(s)-1]
	}
	if len(s) == 36 {
		if s[8] != '-' || s[13] != '-' || s[18] != '-' || s[23] != '-' {
			return false
		}
		s = s[:8] + s[9:13] + s[14:18] + s[19:23] + s[24:]
	}
	if len(s) != 32 {
		return false
	}
	for _, r := range s {
		if !isHex(r) {
			return false
		}
	}
	return true
}

func isHex(r rune) bool {
	return r >= '0' && r <= '9' ||
		r >= 'a' && r <= 'f' ||
		r >= 'A' && r <= 'F'
}
