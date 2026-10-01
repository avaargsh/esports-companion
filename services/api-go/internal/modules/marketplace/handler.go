package marketplace

import (
	"errors"
	"net/http"
	"strconv"
	"strings"
	"unicode/utf8"

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
	r.Get("/players", h.listPlayers)
	r.Get("/players/{player_id}", h.getPlayer)
}

func (h Handler) listPlayers(w http.ResponseWriter, r *http.Request) {
	query := ListQuery{Limit: 12}
	values := r.URL.Query()

	if raw, present := values["game_id"]; present {
		value := ""
		if len(raw) > 0 {
			value = raw[0]
		}
		if !httpx.IsUUID(value) {
			httpx.ValidationError(w, "query", "game_id", "Input should be a valid UUID")
			return
		}
		query.GameID = &value
	}

	if raw, present := values["rank"]; present {
		value := ""
		if len(raw) > 0 {
			value = raw[0]
		}
		if utf8.RuneCountInString(value) > 80 {
			httpx.ValidationError(w, "query", "rank", "String should have at most 80 characters")
			return
		}
		// FastAPI receives an empty optional string here; the existing
		// implementation's "if rank" means empty rank does not filter.
		if value != "" {
			query.Rank = &value
		}
	}

	if raw, present := values["limit"]; present {
		value := ""
		if len(raw) > 0 {
			value = raw[0]
		}
		parsed, err := strconv.Atoi(value)
		if err != nil || parsed < 1 || parsed > 50 {
			httpx.ValidationError(w, "query", "limit", "Input should be between 1 and 50")
			return
		}
		query.Limit = parsed
	}

	items, err := h.repo.ListPlayers(r.Context(), query)
	if err != nil {
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_ERROR")
		return
	}
	httpx.JSONValue(w, http.StatusOK, items)
}

func (h Handler) getPlayer(w http.ResponseWriter, r *http.Request) {
	playerID := strings.TrimSpace(chi.URLParam(r, "player_id"))
	if !httpx.IsUUID(playerID) {
		httpx.ValidationError(w, "path", "player_id", "Input should be a valid UUID")
		return
	}

	item, err := h.repo.GetPlayer(r.Context(), playerID)
	if errors.Is(err, ErrPlayerNotFound) {
		httpx.Error(w, http.StatusNotFound, ErrPlayerNotFound.Error())
		return
	}
	if err != nil {
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_ERROR")
		return
	}
	httpx.JSONValue(w, http.StatusOK, item)
}
