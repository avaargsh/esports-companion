package httpx

import (
	"encoding/json"
	"time"
)

// JSONTime mirrors the datetime JSON representation emitted by the FastAPI /
// Pydantic reference: UTC with "Z", no fractional component for exact seconds,
// otherwise exactly six microsecond digits.
type JSONTime struct {
	time.Time
}

func NewJSONTime(value time.Time) JSONTime {
	return JSONTime{Time: value.UTC().Truncate(time.Microsecond)}
}

func (value JSONTime) MarshalJSON() ([]byte, error) {
	t := value.Time.UTC().Truncate(time.Microsecond)
	layout := "2006-01-02T15:04:05Z"
	if t.Nanosecond() != 0 {
		layout = "2006-01-02T15:04:05.000000Z"
	}
	return json.Marshal(t.Format(layout))
}
