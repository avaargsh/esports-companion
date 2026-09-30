package payments

import (
	"errors"
	"net/http"

	"github.com/go-chi/chi/v5"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/auth"
	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/orders"
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
	r.Post("/orders/{order_id}/payments", h.prepare)
	r.Post("/orders/{order_id}/mock-pay", h.mockPay)
}

func (h Handler) prepare(w http.ResponseWriter, r *http.Request) {
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
	values := r.Header.Values("Idempotency-Key")
	if len(values) == 0 {
		httpx.MissingValidationError(w, "header", "Idempotency-Key")
		return
	}

	preparation, err := h.service.Prepare(
		r.Context(),
		principal.User.ID,
		orderID,
		values[0],
	)
	if err != nil {
		h.writePaymentError(w, err)
		return
	}
	httpx.JSONValue(w, http.StatusOK, preparation.Output())
}

func (h Handler) mockPay(w http.ResponseWriter, r *http.Request) {
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
	if h.secure {
		httpx.Error(w, http.StatusForbidden, "MOCK_PAYMENT_DISABLED")
		return
	}

	values := r.Header.Values("Idempotency-Key")
	if len(values) == 0 {
		httpx.MissingValidationError(w, "header", "Idempotency-Key")
		return
	}
	idempotencyKey := values[0]

	order, err := h.service.PayMock(
		r.Context(),
		principal.User.ID,
		orderID,
		idempotencyKey,
	)
	if err != nil {
		h.writePaymentError(w, err)
		return
	}

	httpx.JSONValue(w, http.StatusOK, order)
}

func (h Handler) writePaymentError(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, orders.ErrOrderNotFound):
		httpx.Error(w, http.StatusNotFound, orders.ErrOrderNotFound.Error())
	case errors.Is(err, orders.ErrOrderNotOwned):
		httpx.Error(w, http.StatusForbidden, orders.ErrOrderNotOwned.Error())
	case errors.Is(err, ErrPaymentProviderMissing),
		errors.Is(err, ErrWeChatPaymentCredentialsMissing):
		httpx.Error(w, http.StatusServiceUnavailable, err.Error())
	case errors.Is(err, ErrIdempotencyKeyReused),
		errors.Is(err, ErrOrderNotWaitingPayment),
		errors.Is(err, ErrPaymentAttemptExists),
		errors.Is(err, ErrPaymentPayerNotFound),
		errors.Is(err, ErrPaymentProviderMismatch),
		errors.Is(err, ErrPaymentProviderBadStatus),
		errors.Is(err, ErrDesignatedPlayerNotFound),
		errors.Is(err, ErrWeChatPayerOpenIDRequired),
		errors.Is(err, ErrWeChatPaymentNetwork),
		errors.Is(err, ErrWeChatPaymentInvalidJSON),
		errors.Is(err, ErrWeChatPaymentInvalidResponse),
		errors.Is(err, ErrWeChatPaymentPrivateKeyInvalid),
		errors.Is(err, orders.ErrOrderAlreadyAccepted),
		errors.Is(err, orders.ErrInvalidOrderTransition):
		httpx.Error(w, http.StatusConflict, err.Error())
	default:
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
	}
}
