package refunds

import (
	"errors"
	"io"
	"net/http"
	"strings"

	"github.com/go-chi/chi/v5"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/auth"
	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/orders"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/httpx"
)

type Handler struct {
	service          Service
	authService      auth.Service
	callbackVerifier *WeChatRefundCallbackVerifier
	secure           bool
}

func NewHandler(
	service Service,
	authService auth.Service,
	callbackVerifier *WeChatRefundCallbackVerifier,
	secure bool,
) Handler {
	return Handler{
		service:          service,
		authService:      authService,
		callbackVerifier: callbackVerifier,
		secure:           secure,
	}
}

func (h Handler) Register(r chi.Router) {
	r.Post("/admin/refunds/{refund_id}/submit", h.submit)
	r.Post("/admin/refunds/{refund_id}/reconcile", h.reconcile)
	r.Post("/refunds/wechat/callback", h.wechatCallback)
}

func (h Handler) wechatCallback(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(r.Body)
	if err != nil {
		h.writeCallbackFailure(w, ErrWeChatRefundCallbackInvalidJSON)
		return
	}
	if h.callbackVerifier == nil {
		h.writeCallbackFailure(w, ErrWeChatRefundCallbackConfigMissing)
		return
	}

	headers := make(map[string]string, len(r.Header))
	for key, values := range r.Header {
		if len(values) > 0 {
			headers[key] = values[0]
		}
	}
	callback, err := h.callbackVerifier.VerifyAndDecrypt(
		r.Context(),
		headers,
		body,
	)
	if err == nil {
		_, err = h.service.ApplyVerifiedCallback(r.Context(), callback)
	}
	if err != nil {
		if isRefundCallbackBusinessError(err) {
			h.writeCallbackFailure(w, err)
			return
		}
		httpx.JSONValue(w, http.StatusInternalServerError, map[string]string{
			"code":    "FAIL",
			"message": "INTERNAL_SERVER_ERROR",
		})
		return
	}
	httpx.JSONValue(w, http.StatusOK, map[string]string{
		"code":    "SUCCESS",
		"message": "成功",
	})
}

func (h Handler) writeCallbackFailure(w http.ResponseWriter, err error) {
	httpx.JSONValue(w, http.StatusBadRequest, map[string]string{
		"code":    "FAIL",
		"message": err.Error(),
	})
}

func (h Handler) reconcile(w http.ResponseWriter, r *http.Request) {
	if _, requestErr := auth.RequirePlatform(h.authService, h.secure, r); requestErr != nil {
		auth.WriteRequestError(w, requestErr)
		return
	}
	refundID := chi.URLParam(r, "refund_id")
	if !httpx.IsUUID(refundID) {
		httpx.ValidationError(w, "path", "refund_id", "Input should be a valid UUID")
		return
	}
	refund, err := h.service.Reconcile(r.Context(), refundID)
	if err != nil {
		h.writeError(w, err)
		return
	}
	httpx.JSONValue(w, http.StatusOK, refund)
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
		ErrRefundProviderQueryUnsupported,
		ErrRefundNotReconcilable,
		ErrRefundProviderIDMismatch,
		ErrRefundQueryOutRefundNoMismatch,
		ErrRefundQueryOrderNoMismatch,
		ErrRefundQueryPaymentTxnMismatch,
		ErrRefundQueryAmountMismatch,
		ErrRefundOrderNotFound,
		ErrWeChatRefundQueryNetwork,
		ErrWeChatRefundQueryInvalidJSON,
		ErrWeChatRefundQueryInvalidResponse,
		ErrWeChatRefundQueryHTTP,
		orders.ErrInvalidOrderTransition,
	} {
		if errors.Is(err, target) {
			return true
		}
	}
	return strings.HasPrefix(err.Error(), "WECHAT_REFUND_HTTP_ERROR:") ||
		strings.HasPrefix(err.Error(), "WECHAT_REFUND_QUERY_HTTP_ERROR:")
}

func isRefundCallbackBusinessError(err error) bool {
	for _, target := range []error{
		ErrWeChatRefundCallbackConfigMissing,
		ErrWeChatRefundCallbackHeadersMissing,
		ErrWeChatRefundCallbackSerialUnknown,
		ErrWeChatRefundCallbackTimestampInvalid,
		ErrWeChatRefundCallbackTimestampExpired,
		ErrWeChatRefundCallbackSignatureInvalid,
		ErrWeChatRefundCallbackInvalidJSON,
		ErrWeChatRefundCallbackEventUnsupported,
		ErrWeChatRefundCallbackResourceMissing,
		ErrWeChatRefundCallbackAlgorithmUnsupported,
		ErrWeChatRefundCallbackResourceTypeInvalid,
		ErrWeChatRefundCallbackResourceInvalid,
		ErrWeChatRefundCallbackDecryptFailed,
		ErrWeChatRefundCallbackMchIDMismatch,
		ErrWeChatRefundCallbackStatusMismatch,
		ErrWeChatRefundCallbackAmountInvalid,
		ErrWeChatRefundCallbackIdentifiersMissing,
		ErrRefundNotFound,
		ErrRefundProviderMismatch,
		ErrRefundOrderNotFound,
		ErrRefundOrderNoMismatch,
		ErrRefundTotalAmountMismatch,
		ErrRefundAmountMismatch,
		ErrRefundPaymentTxnMismatch,
		ErrRefundProviderIDMismatch,
		ErrOrderNotRefunding,
		orders.ErrInvalidOrderTransition,
	} {
		if errors.Is(err, target) {
			return true
		}
	}
	return false
}
