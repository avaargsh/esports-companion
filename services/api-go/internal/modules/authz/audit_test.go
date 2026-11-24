package authz

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgconn"
)

type fakeAuditTx struct {
	calls int
	query string
	args  []any
}

func (f *fakeAuditTx) Exec(_ context.Context, query string, args ...any) (pgconn.CommandTag, error) {
	f.calls++
	f.query = query
	f.args = append([]any(nil), args...)
	return pgconn.CommandTag{}, nil
}

func TestRecordDecisionWritesAuditOutboxEvent(t *testing.T) {
	tx := &fakeAuditTx{}
	repository := AuditRepository{tx: tx}
	decision := referenceDecision()
	authority := referenceAuthority()

	if err := repository.RecordDecision(context.Background(), decision, &authority); err != nil {
		t.Fatal(err)
	}
	if tx.calls != 1 {
		t.Fatalf("expected one outbox insert, got %d", tx.calls)
	}
	if !strings.Contains(tx.query, "INSERT INTO outbox_events") {
		t.Fatalf("unexpected SQL: %s", tx.query)
	}
	if tx.args[1] != fmt.Sprintf("%s:%s", decision.ResourceType, decision.ResourceID) {
		t.Fatalf("unexpected aggregate id: %v", tx.args[1])
	}
	if tx.args[2] != "AUTHORIZATION_DECISION" {
		t.Fatalf("unexpected event type: %v", tx.args[2])
	}

	payloadText, ok := tx.args[3].(string)
	if !ok {
		t.Fatalf("expected JSON string payload, got %T", tx.args[3])
	}
	var payload map[string]any
	if err := json.Unmarshal([]byte(payloadText), &payload); err != nil {
		t.Fatal(err)
	}
	if payload["decision"] != "ALLOW" {
		t.Fatalf("unexpected decision payload: %#v", payload)
	}
	envelope, ok := payload["authorityEnvelope"].(map[string]any)
	if !ok || envelope["authorityDigest"] == "" {
		t.Fatalf("missing authority envelope evidence: %#v", payload)
	}
}

func TestRecordAdmissionWritesAuthorityAndAdmissionEvidence(t *testing.T) {
	tx := &fakeAuditTx{}
	repository := AuditRepository{tx: tx}
	authority := referenceAuthority()
	admission := AuthorityAdmissionDecision{
		AuthorityDigest: authorityDigestForTest(t, authority),
		Decision:        "DENY",
		ReasonCode:      "AUTHORITY_STATE_DRIFT",
		CurrentState:    map[string]any{"walletVersion": 8},
		CurrentResourceVersion: "withdrawal:201:status=PENDING;wallet:401:v8",
		RequestedWrite:  authority.BoundedWrite,
		StateDiff: map[string]DiffValue{
			"walletVersion": {Expected: 7, Current: 8},
		},
		WriteDiff:        map[string]DiffValue{},
		AdmissionVersion: AuthorityAdmissionVersion,
		AdmittedAt:       "2026-09-30T00:00:02+00:00",
	}

	if err := repository.RecordAdmission(context.Background(), authority, admission); err != nil {
		t.Fatal(err)
	}
	if tx.calls != 1 {
		t.Fatalf("expected one outbox insert, got %d", tx.calls)
	}
	if tx.args[2] != "AUTHORITY_ADMISSION" {
		t.Fatalf("unexpected event type: %v", tx.args[2])
	}

	payloadText, ok := tx.args[3].(string)
	if !ok {
		t.Fatalf("expected JSON string payload, got %T", tx.args[3])
	}
	var payload map[string]any
	if err := json.Unmarshal([]byte(payloadText), &payload); err != nil {
		t.Fatal(err)
	}
	envelope, ok := payload["authorityEnvelope"].(map[string]any)
	if !ok || envelope["authorityDigest"] != admission.AuthorityDigest {
		t.Fatalf("authority digest missing or inconsistent: %#v", payload)
	}
	admissionPayload, ok := payload["admission"].(map[string]any)
	if !ok || admissionPayload["reasonCode"] != "AUTHORITY_STATE_DRIFT" {
		t.Fatalf("admission evidence missing: %#v", payload)
	}
}

func authorityDigestForTest(t *testing.T, authority AuthorityEnvelope) string {
	t.Helper()
	digest, err := authority.Digest()
	if err != nil {
		t.Fatal(err)
	}
	return digest
}
