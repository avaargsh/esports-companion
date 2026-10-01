package catalog

import (
	"errors"
	"net/http"

	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/httpx"
	"github.com/go-chi/chi/v5"
)

type Handler struct {
	repo Repository
}

func NewHandler(repo Repository) Handler {
	return Handler{repo: repo}
}

func (h Handler) Register(r chi.Router) {
	r.Get("/games", h.listGames)
	r.Get("/games/{game_id}/skus", h.listSKUs)
}

func (h Handler) listGames(w http.ResponseWriter, r *http.Request) {
	items, err := h.repo.ListGames(r.Context())
	if err != nil {
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_ERROR")
		return
	}
	httpx.JSONValue(w, http.StatusOK, items)
}

func (h Handler) listSKUs(w http.ResponseWriter, r *http.Request) {
	gameID := chi.URLParam(r, "game_id")
	if !httpx.IsUUID(gameID) {
		httpx.ValidationError(w, "path", "game_id", "Input should be a valid UUID")
		return
	}

	items, err := h.repo.ListSKUs(r.Context(), gameID)
	if errors.Is(err, ErrGameNotFound) {
		httpx.Error(w, http.StatusNotFound, ErrGameNotFound.Error())
		return
	}
	if err != nil {
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_ERROR")
		return
	}
	httpx.JSONValue(w, http.StatusOK, items)
}
