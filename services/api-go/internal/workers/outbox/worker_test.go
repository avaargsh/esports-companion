package outbox

import (
	"reflect"
	"testing"
)

func TestBuildMessageMatchesRealtimeContract(t *testing.T) {
	item := event{
		ID:        "event-1",
		EventType: "PAYMENT_SUCCESS",
		Payload: map[string]any{
			"orderId":  "order-1",
			"status":   "PAID",
			"provider": "WECHAT",
		},
	}
	got := buildMessage(item)
	want := map[string]any{
		"type":      "order.status_changed",
		"eventId":   "event-1",
		"eventType": "PAYMENT_SUCCESS",
		"orderId":   "order-1",
		"status":    "PAID",
		"provider":  "WECHAT",
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("message = %#v, want %#v", got, want)
	}
}

func TestBuildMessageUsesMessageTypeForChatEvent(t *testing.T) {
	got := buildMessage(event{
		ID:        "event-2",
		EventType: "ORDER_MESSAGE_CREATED",
		Payload:   map[string]any{"messageId": "message-1"},
	})
	if got["type"] != "order.message_created" {
		t.Fatalf("message type = %#v", got["type"])
	}
}

func TestPayloadCanPreserveReferenceOverrideSemantics(t *testing.T) {
	got := buildMessage(event{
		ID:        "event-3",
		EventType: "CUSTOM",
		Payload: map[string]any{
			"type": "custom.type",
		},
	})
	if got["type"] != "custom.type" {
		t.Fatalf("payload override = %#v", got["type"])
	}
}

func TestRealtimeChannelNamesAreNamespaced(t *testing.T) {
	if got := orderChannel("order-1"); got != "realtime:order:order-1" {
		t.Fatalf("order channel = %q", got)
	}
	if got := userChannel("user-1"); got != "realtime:user:user-1" {
		t.Fatalf("user channel = %q", got)
	}
}
