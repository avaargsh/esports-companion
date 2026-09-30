package payments

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
	callbackVerifier *WeChatCallbackVerifier
	secure           bool
}

func NewHandler(
	service Service,
	authService auth.Service,
	callbackVerifier *WeChatCallbackVerifier,
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
	r.Post("/orders/{order_id}/payments", h.prepare)
	r.Post("/orders/{order_id}/mock-pay", h.mockPay)
	r.Post("/payments/wechat/callback", h.wechatCallback)
}

func (h Handler) wechatCallback(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(r.Body)
	if err != nil {
		httpx.JSONValue(w, http.StatusBadRequest, map[string]string{
			"code":    "FAIL",
			"message": ErrWeChatCallbackInvalidJSON.Error(),
		})
		return
	}
	if h.callbackVerifier == nil {
		httpx.JSONValue(w, http.StatusBadRequest, map[string]string{
			"code":    "FAIL",
			"message": ErrWeChatCallbackConfigMissing.Error(),
		})
		return
	}

	headers := make(map[string]string, len(r.Header))
	for key, values := range r.Header {
		if len(values) > 0 {
			headers[key] = values[0]
		}
	}
	verified, err := h.callbackVerifier.VerifyAndDecrypt(
		r.Context(),
		headers,
		body,
	)
	if err == nil {
		_, err = h.service.ApplyVerifiedSuccess(r.Context(), verified)
	}
	if err != nil {
		if isCallbackBusinessError(err) {
			httpx.JSONValue(w, http.StatusBadRequest, map[string]string{
				"code":    "FAIL",
				"message": err.Error(),
			})
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

func isCallbackBusinessError(err error) bool {
	if strings.HasPrefix(err.Error(), "ORDER_NOT_PAYABLE:") ||
		strings.HasPrefix(err.Error(), "WECHAT_PAY_API_V3_KEY_MUST_BE_32_BYTES") ||
		strings.HasPrefix(err.Error(), "WECHAT_CALLBACK_CERTIFICATE_INVALID") {
		return true
	}
	for _, target := range []error{
		ErrWeChatCallbackConfigMissing,
		ErrWeChatCallbackHeadersMissing,
		ErrWeChatCallbackSerialUnknown,
		ErrWeChatCallbackTimestampInvalid,
		ErrWeChatCallbackTimestampExpired,
		ErrWeChatCallbackSignatureInvalid,
		ErrWeChatCallbackInvalidJSON,
		ErrWeChatCallbackResourceMissing,
		ErrWeChatCallbackAlgorithmUnsupported,
		ErrWeChatCallbackResourceInvalid,
		ErrWeChatCallbackDecryptFailed,
		ErrWeChatCallbackEventUnsupported,
		ErrWeChatCallbackTradeNotSuccess,
		ErrWeChatCallbackAppIDMismatch,
		ErrWeChatCallbackMchIDMismatch,
		ErrWeChatCallbackAmountInvalid,
		ErrWeChatCallbackIdentifiersMissing,
		ErrPaymentOrderNotFound,
		ErrPaymentAmountMismatch,
		ErrPaymentCurrencyMismatch,
		ErrPaymentPayerNotFound,
		ErrPaymentPayerMismatch,
		ErrPaymentProviderTxnReused,
		ErrPaymentPendingTransactionNotFound,
	} {
		if errors.Is(err, target) {
			return true
		}
	}
	return false
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
		errors.Is(err, ErrWeChatPaymentHTTP),
		errors.Is(err, ErrWeChatPaymentPrivateKeyInvalid),
		errors.Is(err, orders.ErrOrderAlreadyAccepted),
		errors.Is(err, orders.ErrInvalidOrderTransition):
		httpx.Error(w, http.StatusConflict, err.Error())
	default:
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
	}
}
