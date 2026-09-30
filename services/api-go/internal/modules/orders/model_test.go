package orders

import (
	"reflect"
	"testing"
)

func TestAvailableActions(t *testing.T) {
	cases := []struct {
		status string
		want   []string
	}{
		{"WAITING_PAYMENT", []string{"PAY", "CANCEL"}},
		{"MATCHING", []string{"REQUEST_REFUND"}},
		{"ACCEPTED", []string{"REQUEST_REFUND", "OPEN_DISPUTE"}},
		{"IN_SERVICE", []string{"OPEN_DISPUTE"}},
		{"FINISH_REQUESTED", []string{"OPEN_DISPUTE"}},
		{"SETTLED", []string{}},
	}
	for _, tc := range cases {
		t.Run(tc.status, func(t *testing.T) {
			if got := availableActions(tc.status); !reflect.DeepEqual(got, tc.want) {
				t.Fatalf("availableActions(%q) = %#v, want %#v", tc.status, got, tc.want)
			}
		})
	}
}
