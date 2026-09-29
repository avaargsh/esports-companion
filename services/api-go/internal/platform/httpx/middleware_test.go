package httpx

import "testing"

func TestIsUUIDMatchesAcceptedTextShapes(t *testing.T) {
	valid := []string{
		"00000000-0000-0000-0000-000000000000",
		"550e8400-e29b-41d4-a716-446655440000",
		"550E8400-E29B-41D4-A716-446655440000",
		"550e8400e29b41d4a716446655440000",
		"{550e8400-e29b-41d4-a716-446655440000}",
		"urn:uuid:550e8400-e29b-41d4-a716-446655440000",
	}
	for _, value := range valid {
		if !IsUUID(value) {
			t.Fatalf("expected valid UUID text: %s", value)
		}
	}

	invalid := []string{
		"",
		"not-a-uuid",
		"550e8400-e29b-41d4-a716446655440000",
		"550e8400e29b41d4a71644665544000z",
		" 550e8400-e29b-41d4-a716-446655440000 ",
	}
	for _, value := range invalid {
		if IsUUID(value) {
			t.Fatalf("expected invalid UUID text: %s", value)
		}
	}
}
