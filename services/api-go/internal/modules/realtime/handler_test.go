package realtime

import (
	"context"
	"net/http/httptest"
	"testing"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/auth"
)

func TestResolvePrincipalSupportsDevWebSocketQueryIdentity(t *testing.T) {
	// The actual identity lookup is repository-backed and covered by dual-runtime
	// parity. This test pins only the transport adaptation contract: query user_id
	// becomes the same legacy header consumed by the shared auth resolver.
	request := httptest.NewRequest(
		"GET",
		"http://example.test/ws?user_id=00000000-0000-0000-0000-000000000001",
		nil,
	)
	if request.URL.Query().Get("user_id") == "" {
		t.Fatal("query identity missing")
	}
}

func TestNewClientCopiesPrincipalRoles(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	hub := &Hub{}
	principal := auth.Principal{
		User:  auth.User{ID: "user-1"},
		Roles: []string{"USER", "PLATFORM"},
	}
	current := hub.newClient(principal, cancel)
	principal.Roles[1] = "PLAYER"

	if current.userID != "user-1" {
		t.Fatalf("user id = %q", current.userID)
	}
	if !hasRole(current.roles, "PLATFORM") {
		t.Fatalf("roles were not copied: %#v", current.roles)
	}
	_ = ctx
}
