package httpx

import (
	"encoding/json"
	"testing"
	"time"
)

func TestJSONTimeMatchesPydanticMicrosecondShape(t *testing.T) {
	value := NewJSONTime(time.Date(2026, 9, 30, 11, 15, 8, 618170000, time.UTC))
	encoded, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	if got, want := string(encoded), ""2026-09-30T11:15:08.618170Z""; got != want {
		t.Fatalf("timestamp = %s, want %s", got, want)
	}
}

func TestJSONTimeOmitsFractionForExactSecond(t *testing.T) {
	value := NewJSONTime(time.Date(2026, 9, 30, 11, 15, 8, 0, time.UTC))
	encoded, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	if got, want := string(encoded), ""2026-09-30T11:15:08Z""; got != want {
		t.Fatalf("timestamp = %s, want %s", got, want)
	}
}
