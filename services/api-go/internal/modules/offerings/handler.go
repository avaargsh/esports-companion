package offerings

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strings"
	"unicode/utf8"

	"github.com/go-chi/chi/v5"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/auth"
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
	r.Get("/player/offerings", h.list)
	r.Put("/player/offerings/{sku_id}", h.upsert)
}

type upsertRequest struct {
	PriceOverride *int   `json:"price_override"`
	Description   string `json:"description"`
	Status        string `json:"status"`
}

func (h Handler) list(w http.ResponseWriter, r *http.Request) {
	principal, requestErr := auth.RequirePlayer(h.authService, h.secure, r)
	if requestErr != nil {
		auth.WriteRequestError(w, requestErr)
		return
	}

	items, err := h.repo.ListForUser(r.Context(), principal.User.ID)
	if errors.Is(err, ErrPlayerProfileNotFound) {
		httpx.Error(w, http.StatusNotFound, err.Error())
		return
	}
	if err != nil {
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
		return
	}
	httpx.JSONValue(w, http.StatusOK, items)
}

func (h Handler) upsert(w http.ResponseWriter, r *http.Request) {
	principal, requestErr := auth.RequirePlayer(h.authService, h.secure, r)
	if requestErr != nil {
		auth.WriteRequestError(w, requestErr)
		return
	}

	skuID := chi.URLParam(r, "sku_id")
	if !httpx.IsUUID(skuID) {
		httpx.ValidationError(w, "path", "sku_id", "Input should be a valid UUID")
		return
	}

	body := upsertRequest{Status: "ACTIVE"}
	if !decodeJSON(w, r, &body) {
		return
	}
	if body.PriceOverride != nil && *body.PriceOverride < 0 {
		httpx.ValidationError(w, "body", "price_override", "Input should be greater than or equal to 0")
		return
	}
	if utf8.RuneCountInString(body.Description) > 1000 {
		httpx.ValidationError(w, "body", "description", "String should have at most 1000 characters")
		return
	}
	status := strings.ToUpper(body.Status)
	if status != "ACTIVE" && status != "INACTIVE" {
		httpx.Error(w, http.StatusConflict, "INVALID_OFFERING_STATUS")
		return
	}

	item, err := h.repo.UpsertForUser(r.Context(), principal.User.ID, skuID, Upsert{
		PriceOverride: body.PriceOverride,
		Description:   body.Description,
		Status:        status,
	})
	switch {
	case errors.Is(err, ErrPlayerProfileNotFound):
		httpx.Error(w, http.StatusNotFound, err.Error())
	case errors.Is(err, ErrSKUNotFound):
		httpx.Error(w, http.StatusNotFound, err.Error())
	case errors.Is(err, ErrOfferingAlreadyExists):
		httpx.Error(w, http.StatusConflict, err.Error())
	case err != nil:
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
	default:
		httpx.JSONValue(w, http.StatusOK, item)
	}
}

func decodeJSON(w http.ResponseWriter, r *http.Request, target any) bool {
	decoder := json.NewDecoder(r.Body)
	if err := decoder.Decode(target); err != nil {
		httpx.ValidationError(w, "body", "", "Invalid JSON body")
		return false
	}
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF {
		httpx.ValidationError(w, "body", "", "Invalid JSON body")
		return false
	}
	return true
}
