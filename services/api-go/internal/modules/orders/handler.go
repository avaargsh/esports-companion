package orders

import (
	"errors"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/auth"
	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/authz"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/httpx"
)

type Handler struct {
	repo        Repository
	authService auth.Service
	secure      bool
}

func NewHandler(repo Repository, authService auth.Service, secure bool) Handler {
	return Handler{
		repo:        repo,
		authService: authService,
		secure:      secure,
	}
}

func (h Handler) Register(r chi.Router) {
	r.Get("/orders", h.list)
	r.Get("/orders/{order_id}", h.get)
	r.Get("/orders/{order_id}/events", h.events)
}

func (h Handler) list(w http.ResponseWriter, r *http.Request) {
	principal, requestErr := auth.ResolvePrincipal(h.authService, h.secure, r)
	if requestErr != nil {
		auth.WriteRequestError(w, requestErr)
		return
	}
	limit, ok := parseLimit(w, r)
	if !ok {
		return
	}
	items, err := h.repo.ListForUser(r.Context(), principal.User.ID, limit)
	if err != nil {
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
		return
	}
	httpx.JSONValue(w, http.StatusOK, items)
}

func (h Handler) get(w http.ResponseWriter, r *http.Request) {
	orderID := chi.URLParam(r, "order_id")
	if !httpx.IsUUID(orderID) {
		httpx.ValidationError(w, "path", "order_id", "Input should be a valid UUID")
		return
	}
	principal, requestErr := auth.ResolvePrincipal(h.authService, h.secure, r)
	if requestErr != nil {
		auth.WriteRequestError(w, requestErr)
		return
	}
	order, err := h.repo.Get(r.Context(), orderID)
	if errors.Is(err, ErrOrderNotFound) {
		httpx.Error(w, http.StatusNotFound, ErrOrderNotFound.Error())
		return
	}
	if err != nil {
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
		return
	}
	if _, err := h.repo.AuthorizeViewer(r.Context(), order, principal); err != nil {
		var denied *authz.ResourceAuthorizationDenied
		if errors.As(err, &denied) {
			httpx.Error(w, http.StatusForbidden, denied.Decision.ReasonCode)
			return
		}
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
		return
	}
	detail, err := h.repo.Detail(r.Context(), order)
	if err != nil {
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
		return
	}
	httpx.JSONValue(w, http.StatusOK, detail)
}

func (h Handler) events(w http.ResponseWriter, r *http.Request) {
	orderID := chi.URLParam(r, "order_id")
	if !httpx.IsUUID(orderID) {
		httpx.ValidationError(w, "path", "order_id", "Input should be a valid UUID")
		return
	}
	principal, requestErr := auth.ResolvePrincipal(h.authService, h.secure, r)
	if requestErr != nil {
		auth.WriteRequestError(w, requestErr)
		return
	}
	order, err := h.repo.Get(r.Context(), orderID)
	if errors.Is(err, ErrOrderNotFound) {
		httpx.Error(w, http.StatusNotFound, ErrOrderNotFound.Error())
		return
	}
	if err != nil {
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
		return
	}
	if _, err := h.repo.AuthorizeViewer(r.Context(), order, principal); err != nil {
		var denied *authz.ResourceAuthorizationDenied
		if errors.As(err, &denied) {
			httpx.Error(w, http.StatusForbidden, denied.Decision.ReasonCode)
			return
		}
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
		return
	}
	items, err := h.repo.Events(r.Context(), order.ID)
	if err != nil {
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
		return
	}
	httpx.JSONValue(w, http.StatusOK, items)
}

func parseLimit(w http.ResponseWriter, r *http.Request) (int, bool) {
	raw, exists := r.URL.Query()["limit"]
	if !exists {
		return 50, true
	}
	if len(raw) == 0 || raw[0] == "" {
		httpx.ValidationError(w, "query", "limit", "Input should be a valid integer")
		return 0, false
	}
	value, err := strconv.Atoi(raw[0])
	if err != nil {
		httpx.ValidationError(w, "query", "limit", "Input should be a valid integer")
		return 0, false
	}
	if value < 1 {
		httpx.ValidationError(w, "query", "limit", "Input should be greater than or equal to 1")
		return 0, false
	}
	if value > 100 {
		httpx.ValidationError(w, "query", "limit", "Input should be less than or equal to 100")
		return 0, false
	}
	return value, true
}
