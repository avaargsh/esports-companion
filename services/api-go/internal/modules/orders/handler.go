package orders

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strconv"
	"unicode/utf8"

	"github.com/go-chi/chi/v5"
	chimiddleware "github.com/go-chi/chi/v5/middleware"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/auth"
	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/authz"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/httpx"
)

type Handler struct {
	service     Service
	authService auth.Service
	secure      bool
}

func NewHandler(service Service, authService auth.Service, secure bool) Handler {
	return Handler{
		service:     service,
		authService: authService,
		secure:      secure,
	}
}

func (h Handler) Register(r chi.Router) {
	r.Get("/orders", h.list)
	r.Post("/orders", h.create)
	r.Post("/player/orders/{order_id}/claim", h.claim)
	r.Post("/player/orders/{order_id}/start", h.start)
	r.Post("/player/orders/{order_id}/finish", h.finish)
	r.Get("/orders/{order_id}", h.get)
	r.Get("/orders/{order_id}/events", h.events)
}

type createRequest struct {
	SKUID      *string `json:"sku_id"`
	OfferingID *string `json:"offering_id"`
	Quantity   *int    `json:"quantity"`
	Remark     *string `json:"remark"`
}

func (h Handler) create(w http.ResponseWriter, r *http.Request) {
	principal, requestErr := auth.ResolvePrincipal(h.authService, h.secure, r)
	if requestErr != nil {
		auth.WriteRequestError(w, requestErr)
		return
	}

	defaultQuantity := 1
	defaultRemark := ""
	body := createRequest{
		Quantity: &defaultQuantity,
		Remark:   &defaultRemark,
	}
	if !decodeJSON(w, r, &body) {
		return
	}
	if body.Quantity == nil {
		httpx.ValidationError(w, "body", "quantity", "Input should be a valid integer")
		return
	}
	if *body.Quantity < 1 {
		httpx.ValidationError(w, "body", "quantity", "Input should be greater than or equal to 1")
		return
	}
	if *body.Quantity > 10 {
		httpx.ValidationError(w, "body", "quantity", "Input should be less than or equal to 10")
		return
	}
	if body.Remark == nil {
		httpx.ValidationError(w, "body", "remark", "Input should be a valid string")
		return
	}
	if utf8.RuneCountInString(*body.Remark) > 500 {
		httpx.ValidationError(w, "body", "remark", "String should have at most 500 characters")
		return
	}
	if body.SKUID != nil && !httpx.IsUUID(*body.SKUID) {
		httpx.ValidationError(w, "body", "sku_id", "Input should be a valid UUID")
		return
	}
	if body.OfferingID != nil && !httpx.IsUUID(*body.OfferingID) {
		httpx.ValidationError(w, "body", "offering_id", "Input should be a valid UUID")
		return
	}

	order, err := h.service.Create(r.Context(), principal.User.ID, CreateInput{
		SKUID:      body.SKUID,
		OfferingID: body.OfferingID,
		Quantity:   *body.Quantity,
		Remark:     *body.Remark,
	})
	if err != nil {
		switch {
		case errors.Is(err, ErrExactlyOneSKUOrOffering),
			errors.Is(err, ErrOfferingNotAvailable),
			errors.Is(err, ErrPlayerNotAvailable),
			errors.Is(err, ErrCannotOrderOwnOffering),
			errors.Is(err, ErrSKUNotAvailable),
			errors.Is(err, ErrGameNotAvailable):
			httpx.Error(w, http.StatusConflict, err.Error())
		default:
			httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
		}
		return
	}
	httpx.JSONValue(w, http.StatusCreated, order)
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

type claimRequest struct {
	ExpectedVersion *int `json:"expected_version"`
}

func (h Handler) claim(w http.ResponseWriter, r *http.Request) {
	principal, requestErr := auth.RequirePlayer(h.authService, h.secure, r)
	if requestErr != nil {
		auth.WriteRequestError(w, requestErr)
		return
	}

	orderID := chi.URLParam(r, "order_id")
	if !httpx.IsUUID(orderID) {
		httpx.ValidationError(w, "path", "order_id", "Input should be a valid UUID")
		return
	}

	body := claimRequest{}
	if !decodeJSON(w, r, &body) {
		return
	}
	if body.ExpectedVersion == nil {
		httpx.ValidationError(w, "body", "expected_version", "Field required")
		return
	}
	if *body.ExpectedVersion < 0 {
		httpx.ValidationError(w, "body", "expected_version", "Input should be greater than or equal to 0")
		return
	}

	order, err := h.service.Claim(
		r.Context(),
		principal.User.ID,
		orderID,
		ClaimInput{ExpectedVersion: *body.ExpectedVersion},
	)
	if err != nil {
		switch {
		case errors.Is(err, ErrOrderNotFound):
			httpx.Error(w, http.StatusNotFound, ErrOrderNotFound.Error())
		case errors.Is(err, ErrOrderAlreadyAccepted),
			errors.Is(err, ErrPlayerNotEligible),
			errors.Is(err, ErrCannotClaimOwnOrder),
			errors.Is(err, ErrPlayerNotOfferingSKU):
			httpx.Error(w, http.StatusConflict, err.Error())
		default:
			httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
		}
		return
	}
	httpx.JSONValue(w, http.StatusOK, order)
}

func (h Handler) start(w http.ResponseWriter, r *http.Request) {
	h.providerLifecycle(w, r, "start")
}

func (h Handler) finish(w http.ResponseWriter, r *http.Request) {
	h.providerLifecycle(w, r, "finish")
}

func (h Handler) providerLifecycle(w http.ResponseWriter, r *http.Request, action string) {
	principal, requestErr := auth.RequirePlayer(h.authService, h.secure, r)
	if requestErr != nil {
		auth.WriteRequestError(w, requestErr)
		return
	}

	orderID := chi.URLParam(r, "order_id")
	if !httpx.IsUUID(orderID) {
		httpx.ValidationError(w, "path", "order_id", "Input should be a valid UUID")
		return
	}

	var (
		order Order
		err   error
	)
	switch action {
	case "start":
		order, err = h.service.Start(r.Context(), principal.User.ID, orderID)
	case "finish":
		order, err = h.service.Finish(r.Context(), principal.User.ID, orderID)
	default:
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
		return
	}
	if err != nil {
		switch {
		case errors.Is(err, ErrOrderNotFound):
			httpx.Error(w, http.StatusNotFound, ErrOrderNotFound.Error())
		case errors.Is(err, ErrAssignmentNotFound):
			httpx.Error(w, http.StatusConflict, ErrAssignmentNotFound.Error())
		case errors.Is(err, ErrNotOrderPlayer):
			httpx.Error(w, http.StatusForbidden, ErrNotOrderPlayer.Error())
		case errors.Is(err, ErrInvalidOrderTransition):
			httpx.Error(w, http.StatusConflict, err.Error())
		default:
			httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
		}
		return
	}
	httpx.JSONValue(w, http.StatusOK, order)
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
	items, err := h.service.ListForUser(r.Context(), principal.User.ID, limit)
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
	detail, err := h.service.DetailForViewer(
		r.Context(),
		orderID,
		principal,
		chimiddleware.GetReqID(r.Context()),
	)
	if err != nil {
		writeReadError(w, err)
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
	items, err := h.service.EventsForViewer(
		r.Context(),
		orderID,
		principal,
		chimiddleware.GetReqID(r.Context()),
	)
	if err != nil {
		writeReadError(w, err)
		return
	}
	httpx.JSONValue(w, http.StatusOK, items)
}

func writeReadError(w http.ResponseWriter, err error) {
	if errors.Is(err, ErrOrderNotFound) {
		httpx.Error(w, http.StatusNotFound, ErrOrderNotFound.Error())
		return
	}
	var denied *authz.ResourceAuthorizationDenied
	if errors.As(err, &denied) {
		httpx.Error(w, http.StatusForbidden, denied.Decision.ReasonCode)
		return
	}
	httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
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
