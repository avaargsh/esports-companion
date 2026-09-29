package auth

import (
	"strings"
	"testing"
	"time"
)

func TestAccessTokenRoundTripAndTamperRejection(t *testing.T) {
	now := time.Unix(1_800_000_000, 0).UTC()
	userID := "11111111-1111-4111-8111-111111111111"
	sessionID := "22222222-2222-4222-8222-222222222222"
	key := "01234567890123456789012345678901"

	token, err := signAccess(
		userID,
		sessionID,
		[]string{"USER", "PLAYER"},
		now,
		15*time.Minute,
		key,
	)
	if err != nil {
		t.Fatalf("sign token: %v", err)
	}

	claims, err := decodeAccess(token, key, now.Add(time.Second))
	if err != nil {
		t.Fatalf("decode token: %v", err)
	}
	if claims.Sub != userID || claims.SID != sessionID || claims.Iss != issuer {
		t.Fatalf("unexpected claims: %+v", claims)
	}

	parts := strings.Split(token, ".")
	parts[2] = "A" + parts[2][1:]
	if _, err := decodeAccess(strings.Join(parts, "."), key, now.Add(time.Second)); err == nil {
		t.Fatal("expected tampered token rejection")
	}
	if _, err := decodeAccess(token, key, now.Add(16*time.Minute)); err == nil {
		t.Fatal("expected expired token rejection")
	}
}

func TestRefreshTokenShapeAndHash(t *testing.T) {
	token, err := newRefreshToken()
	if err != nil {
		t.Fatalf("new refresh token: %v", err)
	}
	if len(token) < 60 {
		t.Fatalf("refresh token unexpectedly short: %d", len(token))
	}
	hash := hashRefresh(token)
	if len(hash) != 64 || hash == token {
		t.Fatalf("unexpected refresh hash: %q", hash)
	}
}
