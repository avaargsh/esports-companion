package realtime

import (
	"context"
	"fmt"
	"testing"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/auth"
)

func TestClientAllowedForOrder(t *testing.T) {
	allowed := map[string]struct{}{
		"customer": {},
		"player":   {},
	}
	cases := []struct {
		name      string
		principal auth.Principal
		want      bool
	}{
		{
			name: "customer",
			principal: auth.Principal{
				User: auth.User{ID: "customer"},
			},
			want: true,
		},
		{
			name: "active player",
			principal: auth.Principal{
				User:  auth.User{ID: "player"},
				Roles: []string{"USER", "PLAYER"},
			},
			want: true,
		},
		{
			name: "platform",
			principal: auth.Principal{
				User:  auth.User{ID: "admin"},
				Roles: []string{"USER", "PLATFORM"},
			},
			want: true,
		},
		{
			name: "unrelated",
			principal: auth.Principal{
				User:  auth.User{ID: "other"},
				Roles: []string{"USER", "PLAYER"},
			},
			want: false,
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			hub := &Hub{}
			current := hub.newClient(tc.principal, cancel)
			if got := clientAllowedForOrder(current, allowed); got != tc.want {
				t.Fatalf("allowed = %v, want %v", got, tc.want)
			}
			_ = ctx
		})
	}
}

func TestClientDeduplicatesEventIDsWithinWindow(t *testing.T) {
	current := &client{
		seen: make(map[string]struct{}, clientDedupeSize),
	}
	if !current.acceptEvent("event-1") {
		t.Fatal("first delivery should be accepted")
	}
	if current.acceptEvent("event-1") {
		t.Fatal("duplicate delivery should be rejected")
	}

	for i := 0; i < clientDedupeSize; i++ {
		current.acceptEvent(fmt.Sprintf("event-%d", i+2))
	}
	if !current.acceptEvent("event-1") {
		t.Fatal("evicted event should be accepted again")
	}
}

func TestRealtimeEventID(t *testing.T) {
	if got := realtimeEventID([]byte(`{"eventId":"event-1","type":"order.status_changed"}`)); got != "event-1" {
		t.Fatalf("event id = %q", got)
	}
	if got := realtimeEventID([]byte("not-json")); got != "" {
		t.Fatalf("invalid payload event id = %q", got)
	}
}
