package auth

import (
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"unicode/utf8"

	"github.com/go-chi/chi/v5"

	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/httpx"
)

type Handler struct {
	service Service
	secure  bool
}

func NewHandler(service Service, secure bool) Handler {
	return Handler{service: service, secure: secure}
}

func (h Handler) Register(r chi.Router) {
	r.Route("/auth", func(r chi.Router) {
		r.Post("/wechat/login", h.login)
		r.Post("/refresh", h.refresh)
		r.Post("/logout", h.logout)
		r.Get("/me", h.me)
	})
}

type loginRequest struct {
	Code string `json:"code"`
}

type refreshRequest struct {
	RefreshToken string `json:"refreshToken"`
}

type loginResponse struct {
	UserID           string   `json:"userId"`
	Provider         string   `json:"provider"`
	IsNewUser        bool     `json:"isNewUser"`
	Roles            []string `json:"roles"`
	TokenType        string   `json:"tokenType"`
	AccessToken      string   `json:"accessToken"`
	RefreshToken     string   `json:"refreshToken"`
	ExpiresIn        int      `json:"expiresIn"`
	RefreshExpiresIn int      `json:"refreshExpiresIn"`
}

type refreshResponse struct {
	UserID           string   `json:"userId"`
	Roles            []string `json:"roles"`
	TokenType        string   `json:"tokenType"`
	AccessToken      string   `json:"accessToken"`
	RefreshToken     string   `json:"refreshToken"`
	ExpiresIn        int      `json:"expiresIn"`
	RefreshExpiresIn int      `json:"refreshExpiresIn"`
}

type meResponse struct {
	UserID string   `json:"userId"`
	Roles  []string `json:"roles"`
	Status string   `json:"status"`
}

func (h Handler) login(w http.ResponseWriter, r *http.Request) {
	var body loginRequest
	if !decodeJSON(w, r, &body) {
		return
	}
	length := utf8.RuneCountInString(body.Code)
	if length < 1 {
		httpx.ValidationError(w, "body", "code", "String should have at least 1 character")
		return
	}
	if length > 256 {
		httpx.ValidationError(w, "body", "code", "String should have at most 256 characters")
		return
	}

	user, created, tokens, err := h.service.Login(r.Context(), body.Code)
	if err != nil {
		if isLoginUnavailable(err) {
			httpx.Error(w, http.StatusServiceUnavailable, err.Error())
			return
		}
		if isLoginAuthError(err) {
			httpx.Error(w, http.StatusUnauthorized, err.Error())
			return
		}
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
		return
	}

	httpx.JSONValue(w, http.StatusOK, loginResponse{
		UserID: user.ID, Provider: h.service.ProviderName(), IsNewUser: created,
		Roles: tokens.Roles, TokenType: tokens.TokenType,
		AccessToken: tokens.AccessToken, RefreshToken: tokens.RefreshToken,
		ExpiresIn: tokens.ExpiresIn, RefreshExpiresIn: tokens.RefreshExpiresIn,
	})
}

func (h Handler) refresh(w http.ResponseWriter, r *http.Request) {
	var body refreshRequest
	if !decodeJSON(w, r, &body) {
		return
	}
	if !validateRefreshTokenInput(w, body.RefreshToken) {
		return
	}

	tokens, err := h.service.Refresh(r.Context(), body.RefreshToken)
	if err != nil {
		if isRefreshAuthError(err) {
			httpx.Error(w, http.StatusUnauthorized, err.Error())
			return
		}
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
		return
	}

	httpx.JSONValue(w, http.StatusOK, refreshResponse{
		UserID: tokens.UserID, Roles: tokens.Roles, TokenType: tokens.TokenType,
		AccessToken: tokens.AccessToken, RefreshToken: tokens.RefreshToken,
		ExpiresIn: tokens.ExpiresIn, RefreshExpiresIn: tokens.RefreshExpiresIn,
	})
}

func (h Handler) logout(w http.ResponseWriter, r *http.Request) {
	var body refreshRequest
	if !decodeJSON(w, r, &body) {
		return
	}
	if !validateRefreshTokenInput(w, body.RefreshToken) {
		return
	}
	if err := h.service.Logout(r.Context(), body.RefreshToken); err != nil {
		httpx.Error(w, http.StatusInternalServerError, "INTERNAL_SERVER_ERROR")
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (h Handler) me(w http.ResponseWriter, r *http.Request) {
	principal, requestErr := ResolvePrincipal(h.service, h.secure, r)
	if requestErr != nil {
		WriteRequestError(w, requestErr)
		return
	}
	httpx.JSONValue(w, http.StatusOK, meResponse{
		UserID: principal.User.ID,
		Roles:  principal.Roles,
		Status: principal.User.Status,
	})
}

func ResolvePrincipal(service Service, secure bool, r *http.Request) (Principal, *RequestError) {
	xUserID := r.Header.Get("X-User-Id")
	xAdminID := r.Header.Get("X-Admin-Id")
	for field, value := range map[string]string{
		"X-User-Id":  xUserID,
		"X-Admin-Id": xAdminID,
	} {
		if value != "" && !httpx.IsUUID(value) {
			return Principal{}, &RequestError{
				Status: http.StatusUnprocessableEntity, Location: "header",
				Field: field, Message: "Input should be a valid UUID",
			}
		}
	}

	authorization := r.Header.Get("Authorization")
	if authorization != "" {
		scheme, token, found := strings.Cut(authorization, " ")
		if !found || !strings.EqualFold(scheme, "Bearer") || token == "" {
			return Principal{}, &RequestError{
				Status: http.StatusUnauthorized,
				Code:   "BEARER_TOKEN_REQUIRED",
			}
		}
		principal, err := service.Authenticate(r.Context(), token)
		if err != nil {
			if isAccessAuthError(err) {
				return Principal{}, &RequestError{
					Status: http.StatusUnauthorized,
					Code:   err.Error(),
				}
			}
			return Principal{}, &RequestError{
				Status: http.StatusInternalServerError,
				Code:   "INTERNAL_SERVER_ERROR",
			}
		}
		return principal, nil
	}

	if !secure {
		legacyID := xUserID
		if legacyID == "" {
			legacyID = xAdminID
		}
		if legacyID != "" {
			principal, err := service.LegacyPrincipal(r.Context(), legacyID)
			if err != nil {
				if isAccessAuthError(err) {
					return Principal{}, &RequestError{
						Status: http.StatusUnauthorized,
						Code:   err.Error(),
					}
				}
				return Principal{}, &RequestError{
					Status: http.StatusInternalServerError,
					Code:   "INTERNAL_SERVER_ERROR",
				}
			}
			return principal, nil
		}
	}

	return Principal{}, &RequestError{
		Status: http.StatusUnauthorized,
		Code:   "AUTHENTICATION_REQUIRED",
	}
}

func RequireSession(principal Principal) (Principal, *RequestError) {
	if principal.Legacy || principal.SessionID == "" {
		return Principal{}, &RequestError{
			Status: http.StatusUnauthorized,
			Code:   "SESSION_AUTH_REQUIRED",
		}
	}
	return principal, nil
}

func RequirePlayer(service Service, secure bool, r *http.Request) (Principal, *RequestError) {
	principal, requestErr := ResolvePrincipal(service, secure, r)
	if requestErr != nil {
		return Principal{}, requestErr
	}
	if !principalHasRole(principal, "PLAYER") {
		return Principal{}, &RequestError{
			Status: http.StatusForbidden,
			Code:   "PLAYER_REQUIRED",
		}
	}
	if secure {
		return RequireSession(principal)
	}
	return principal, nil
}

func RequirePlatform(service Service, secure bool, r *http.Request) (Principal, *RequestError) {
	principal, requestErr := ResolvePrincipal(service, secure, r)
	if requestErr != nil {
		return Principal{}, requestErr
	}
	if !principalHasRole(principal, "PLATFORM") {
		return Principal{}, &RequestError{
			Status: http.StatusForbidden,
			Code:   "PLATFORM_REQUIRED",
		}
	}
	if secure {
		return RequireSession(principal)
	}
	return principal, nil
}

func principalHasRole(principal Principal, role string) bool {
	for _, candidate := range principal.Roles {
		if candidate == role {
			return true
		}
	}
	return false
}

func WriteRequestError(w http.ResponseWriter, requestErr *RequestError) {
	if requestErr.Status == http.StatusUnprocessableEntity {
		httpx.ValidationError(
			w,
			requestErr.Location,
			requestErr.Field,
			requestErr.Message,
		)
		return
	}
	httpx.Error(w, requestErr.Status, requestErr.Code)
}

func validateRefreshTokenInput(w http.ResponseWriter, value string) bool {
	length := utf8.RuneCountInString(value)
	if length < 20 {
		httpx.ValidationError(w, "body", "refreshToken", "String should have at least 20 characters")
		return false
	}
	if length > 512 {
		httpx.ValidationError(w, "body", "refreshToken", "String should have at most 512 characters")
		return false
	}
	return true
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

func isLoginUnavailable(err error) bool {
	message := err.Error()
	return strings.HasPrefix(message, "AUTH_PROVIDER_NOT_CONFIGURED") ||
		strings.HasPrefix(message, "WECHAT_AUTH_CREDENTIALS_MISSING") ||
		strings.HasPrefix(message, "PRODUCTION_SESSION_SIGNING_KEY_REQUIRED")
}

func isLoginAuthError(err error) bool {
	message := err.Error()
	prefixes := []string{
		"INVALID_MOCK_LOGIN_CODE",
		"WECHAT_LOGIN_CODE_REQUIRED",
		"WECHAT_CODE_EXCHANGE_NETWORK_ERROR",
		"WECHAT_CODE_EXCHANGE_HTTP_ERROR:",
		"WECHAT_CODE_EXCHANGE_INVALID_JSON",
		"WECHAT_CODE_EXCHANGE_FAILED:",
		"WECHAT_CODE_EXCHANGE_INVALID_RESPONSE",
	}
	for _, prefix := range prefixes {
		if strings.HasPrefix(message, prefix) {
			return true
		}
	}
	return false
}

func isRefreshAuthError(err error) bool {
	switch err.Error() {
	case "REFRESH_TOKEN_INVALID", "REFRESH_TOKEN_REUSED",
		"REFRESH_TOKEN_EXPIRED", "USER_INACTIVE",
		"PRODUCTION_SESSION_SIGNING_KEY_REQUIRED":
		return true
	default:
		return false
	}
}

func isAccessAuthError(err error) bool {
	switch err.Error() {
	case "BEARER_TOKEN_REQUIRED", "AUTHENTICATION_REQUIRED",
		"ACCESS_TOKEN_INVALID", "ACCESS_SESSION_INVALID",
		"ACCESS_SESSION_REVOKED", "ACCESS_SESSION_EXPIRED",
		"USER_INACTIVE", "LEGACY_USER_INVALID",
		"PRODUCTION_SESSION_SIGNING_KEY_REQUIRED":
		return true
	default:
		return false
	}
}
