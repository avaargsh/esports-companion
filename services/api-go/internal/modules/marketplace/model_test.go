package marketplace

import (
	"encoding/json"
	"testing"
)

func TestPlayerAvailableActions(t *testing.T) {
	tests := []struct {
		name   string
		status string
		offers []Offering
		want   string
	}{
		{"available with offering", "AVAILABLE", []Offering{{}}, `["CREATE_DESIGNATED_ORDER"]`},
		{"available without offerings", "AVAILABLE", nil, `[]`},
		{"busy with offering", "BUSY", []Offering{{}}, `[]`},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			player := Player{ServiceStatus: tt.status, Offerings: tt.offers}
			player.setAvailableActions()
			payload, err := json.Marshal(player)
			if err != nil {
				t.Fatal(err)
			}
			var fields map[string]json.RawMessage
			if err := json.Unmarshal(payload, &fields); err != nil {
				t.Fatal(err)
			}
			if got := string(fields["available_actions"]); got != tt.want {
				t.Fatalf("available_actions = %s, want %s", got, tt.want)
			}
		})
	}
}
