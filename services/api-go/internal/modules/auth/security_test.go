package auth

import (
	"net/http"
	"testing"
)

func TestRequireSessionRejectsLegacyPrincipal(t *testing.T) {
	_, requestErr := RequireSession(Principal{
		User:   User{ID: "user-1"},
		Roles:  []string{"USER", "PLATFORM"},
		Legacy: true,
	})
	if requestErr == nil {
		t.Fatal("expected session requirement failure")
	}
	if requestErr.Status != http.StatusUnauthorized || requestErr.Code != "SESSION_AUTH_REQUIRED" {
		t.Fatalf("unexpected request error: %#v", requestErr)
	}
}

func TestRequireSessionAcceptsAuthenticatedSession(t *testing.T) {
	principal := Principal{
		User:      User{ID: "user-1"},
		Roles:     []string{"USER"},
		SessionID: "session-1",
	}
	got, requestErr := RequireSession(principal)
	if requestErr != nil {
		t.Fatal(requestErr)
	}
	if got.SessionID != "session-1" {
		t.Fatalf("unexpected principal: %#v", got)
	}
}

func TestPrincipalHasRole(t *testing.T) {
	principal := Principal{Roles: []string{"USER", "PLAYER"}}
	if !principalHasRole(principal, "PLAYER") {
		t.Fatal("expected PLAYER role")
	}
	if principalHasRole(principal, "PLATFORM") {
		t.Fatal("did not expect PLATFORM role")
	}
}
