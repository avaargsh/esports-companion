package auth

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"strings"
	"time"
)

const (
	issuer        = "esports-companion"
	devSigningKey = "dev-only-change-me-use-at-least-32-bytes"
)

type accessClaims struct {
	Sub   string   `json:"sub"`
	SID   string   `json:"sid"`
	Type  string   `json:"type"`
	Roles []string `json:"roles,omitempty"`
	Iat   int64    `json:"iat"`
	Exp   int64    `json:"exp"`
	Iss   string   `json:"iss"`
	JTI   string   `json:"jti,omitempty"`
}

func validateSigningKey(secure bool, key string) error {
	if secure && (key == devSigningKey || len(key) < 32) {
		return errors.New("PRODUCTION_SESSION_SIGNING_KEY_REQUIRED")
	}
	return nil
}

func signAccess(userID, sessionID string, roles []string, now time.Time, ttl time.Duration, key string) (string, error) {
	jti, err := randomHex(16)
	if err != nil {
		return "", err
	}
	header, err := json.Marshal(map[string]string{"alg": "HS256", "typ": "JWT"})
	if err != nil {
		return "", err
	}
	claims, err := json.Marshal(accessClaims{
		Sub: userID, SID: sessionID, Type: "access", Roles: roles,
		Iat: now.Unix(), Exp: now.Add(ttl).Unix(), Iss: issuer, JTI: jti,
	})
	if err != nil {
		return "", err
	}
	encodedHeader := base64.RawURLEncoding.EncodeToString(header)
	encodedClaims := base64.RawURLEncoding.EncodeToString(claims)
	unsigned := encodedHeader + "." + encodedClaims
	mac := hmac.New(sha256.New, []byte(key))
	_, _ = mac.Write([]byte(unsigned))
	signature := base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
	return unsigned + "." + signature, nil
}

func decodeAccess(token, key string, now time.Time) (accessClaims, error) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return accessClaims{}, errors.New("ACCESS_TOKEN_INVALID")
	}

	var header struct {
		Alg string `json:"alg"`
	}
	headerBytes, err := base64.RawURLEncoding.DecodeString(parts[0])
	if err != nil || json.Unmarshal(headerBytes, &header) != nil || header.Alg != "HS256" {
		return accessClaims{}, errors.New("ACCESS_TOKEN_INVALID")
	}

	unsigned := parts[0] + "." + parts[1]
	mac := hmac.New(sha256.New, []byte(key))
	_, _ = mac.Write([]byte(unsigned))
	expected := mac.Sum(nil)
	actual, err := base64.RawURLEncoding.DecodeString(parts[2])
	if err != nil || !hmac.Equal(actual, expected) {
		return accessClaims{}, errors.New("ACCESS_TOKEN_INVALID")
	}

	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return accessClaims{}, errors.New("ACCESS_TOKEN_INVALID")
	}
	var claims accessClaims
	if err := json.Unmarshal(payload, &claims); err != nil {
		return accessClaims{}, errors.New("ACCESS_TOKEN_INVALID")
	}
	if claims.Iss != issuer || claims.Type != "access" ||
		claims.Sub == "" || claims.SID == "" ||
		claims.Iat == 0 || claims.Exp == 0 ||
		!isUUID(claims.Sub) || !isUUID(claims.SID) ||
		claims.Exp <= now.Unix() || claims.Iat > now.Unix() {
		return accessClaims{}, errors.New("ACCESS_TOKEN_INVALID")
	}
	return claims, nil
}

func newUUID() (string, error) {
	raw := make([]byte, 16)
	if _, err := rand.Read(raw); err != nil {
		return "", err
	}
	raw[6] = (raw[6] & 0x0f) | 0x40
	raw[8] = (raw[8] & 0x3f) | 0x80
	hexed := hex.EncodeToString(raw)
	return hexed[0:8] + "-" + hexed[8:12] + "-" + hexed[12:16] + "-" + hexed[16:20] + "-" + hexed[20:32], nil
}

func newRefreshToken() (string, error) {
	raw := make([]byte, 48)
	if _, err := rand.Read(raw); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(raw), nil
}

func hashRefresh(token string) string {
	sum := sha256.Sum256([]byte(token))
	return hex.EncodeToString(sum[:])
}

func randomHex(size int) (string, error) {
	raw := make([]byte, size)
	if _, err := rand.Read(raw); err != nil {
		return "", err
	}
	return hex.EncodeToString(raw), nil
}

func isUUID(value string) bool {
	if len(value) != 36 ||
		value[8] != '-' || value[13] != '-' || value[18] != '-' || value[23] != '-' {
		return false
	}
	for i, r := range value {
		if i == 8 || i == 13 || i == 18 || i == 23 {
			continue
		}
		if !((r >= '0' && r <= '9') || (r >= 'a' && r <= 'f') || (r >= 'A' && r <= 'F')) {
			return false
		}
	}
	return true
}
