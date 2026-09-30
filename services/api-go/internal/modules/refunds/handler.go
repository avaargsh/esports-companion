package refunds

import (
	"errors"
	"net/http"
	"strings"

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
	r.Post("/admin/refunds/{refund_id}/submit", h.submit)
}

func (h Handler) submit(w http.ResponseWriter, r *http.Request) {
	if _, requestErr := auth.RequirePlatform(h.authService, h.secure, r); requestErr != nil {
		auth.WriteRequestError(w, requestErr)
		return
	}
	refundID := chi.URLParam(r, "refund_id")
	if !httpx.IsUUID(refundID) {
		httpx.ValidationError(w, "path", "refund_id", "Input should be a valid UUID")
		return
	}

	refund, err := h.service.Submit(r.Context(), refundID)
	if err != nil {
		h.writeError(w, err)
		return
	}
	httpx.JSONValue(w, http.StatusOK, refund)
}

func (h Handler) writeError(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, ErrRefundNotFound):
		httpx.Error(w, http.StatusNotFound, ErrRefundNotFound.Error())
	case errors.Is(err, ErrRefundProviderMissing),
		errors.Is(err, ErrWeChatRefundCredentialsMissing):
		httpx.Error(w, http.StatusServiceUnavailable, err.Error())
	case isRefundConflict(err):
		httpx.Error(w, http.StatusConflict, err.Error())
	default:
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
	}
}

func isRefundConflict(err error) bool {
	for _, target := range []error{
		ErrRefundNotSubmittable,
		ErrOrderNotRefunding,
		ErrSuccessfulPaymentNotFound,
		ErrRefundProviderMismatch,
		ErrWeChatRefundRequiresPayment,
		ErrWeChatPaymentTxnMissing,
		ErrRefundOutRefundNoMissing,
		ErrWeChatRefundNetwork,
		ErrWeChatRefundInvalidJSON,
		ErrWeChatRefundInvalidResponse,
		ErrWeChatRefundStatusInvalid,
		ErrWeChatRefundHTTP,
		ErrWeChatRefundSignatureHeaders,
		ErrWeChatRefundSerialUnknown,
		ErrWeChatRefundSignatureInvalid,
		ErrWeChatRefundPrivateKeyInvalid,
		ErrWeChatRefundCertificateInvalid,
		orders.ErrInvalidOrderTransition,
	} {
		if errors.Is(err, target) {
			return true
		}
	}
	return strings.HasPrefix(err.Error(), "WECHAT_REFUND_HTTP_ERROR:")
}
