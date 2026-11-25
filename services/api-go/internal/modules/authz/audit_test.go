package authz

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgconn"
)

type fakeAuditTx struct {
	calls int
	query string
	args  []any
	err   error
}

func (f *fakeAuditTx) Exec(_ context.Context, query string, args ...any) (pgconn.CommandTag, error) {
	f.calls++
	f.query = query
	f.args = append([]any(nil), args...)
	return pgconn.CommandTag{}, f.err
}

func (f *fakeAuditTx) Commit(context.Context) error {
	return nil
}

func (f *fakeAuditTx) Rollback(context.Context) error {
	return nil
}

var _ auditTransaction = (*fakeAuditTx)(nil)

func TestRecordDecisionWritesAuditOutboxEvent(t *testing.T) {
	tx := &fakeAuditTx{}
	repository, err := NewAuditRepository(tx)
	if err != nil {
		t.Fatal(err)
	}
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
	repository, err := NewAuditRepository(tx)
	if err != nil {
		t.Fatal(err)
	}
	authority := referenceAuthority()
	admission := AuthorityAdmissionDecision{
		AuthorityDigest:        authorityDigestForTest(t, authority),
		Decision:               "DENY",
		ReasonCode:             "AUTHORITY_STATE_DRIFT",
		CurrentState:           map[string]any{"walletVersion": 8},
		CurrentResourceVersion: "withdrawal:201:status=PENDING;wallet:401:v8",
		RequestedWrite:         authority.BoundedWrite,
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

func TestNewAuditRepositoryRejectsNilTransaction(t *testing.T) {
	if _, err := NewAuditRepository(nil); err == nil {
		t.Fatal("expected nil transaction rejection")
	}
}

func TestAuditRepositoryWithoutTransactionFailsClosed(t *testing.T) {
	var repository AuditRepository
	if err := repository.RecordDecision(context.Background(), referenceDecision(), nil); err == nil {
		t.Fatal("expected missing transaction error")
	}
}

func TestRecordDecisionPropagatesTransactionFailure(t *testing.T) {
	expected := errors.New("database unavailable")
	repository, err := NewAuditRepository(&fakeAuditTx{err: expected})
	if err != nil {
		t.Fatal(err)
	}
	err = repository.RecordDecision(context.Background(), referenceDecision(), nil)
	if !errors.Is(err, expected) {
		t.Fatalf("expected wrapped transaction error, got %v", err)
	}
}

func TestRecordDecisionRejectsMismatchedAuthorityAuthorization(t *testing.T) {
	tx := &fakeAuditTx{}
	repository, err := NewAuditRepository(tx)
	if err != nil {
		t.Fatal(err)
	}
	decision := referenceDecision()
	authority := referenceAuthority()
	authority.Authorization.Action = "UNRELATED_ACTION"

	err = repository.RecordDecision(context.Background(), decision, &authority)
	if err == nil || !strings.Contains(err.Error(), "does not match") {
		t.Fatalf("expected mismatched authorization to fail closed, got %v", err)
	}
	if tx.calls != 0 {
		t.Fatalf("mismatched authorization must not be persisted, got %d writes", tx.calls)
	}
}

func TestRecordAdmissionRejectsMismatchedAuthorityDigest(t *testing.T) {
	tx := &fakeAuditTx{}
	repository, err := NewAuditRepository(tx)
	if err != nil {
		t.Fatal(err)
	}
	authority := referenceAuthority()
	admission := AuthorityAdmissionDecision{
		AuthorityDigest: "not-the-envelope-digest",
		Decision:        "ADMIT",
		ReasonCode:      "AUTHORITY_EXACT_MATCH",
	}

	err = repository.RecordAdmission(context.Background(), authority, admission)
	if err == nil || !strings.Contains(err.Error(), "digest does not match") {
		t.Fatalf("expected mismatched authority digest to fail closed, got %v", err)
	}
	if tx.calls != 0 {
		t.Fatalf("mismatched admission must not be persisted, got %d writes", tx.calls)
	}
}

// A persisted envelope must remain verifiable using its original JSON number
// representations, rather than losing float identity during the audit write.
func TestAuditPreservesCanonicalEnvelope(t *testing.T) {
	authority := referenceAuthority()
	authority.ExpectedState["ratio"] = float64(1)
	authority.ExpectedState["tiny"] = float64(1e-5)
	authority.ExpectedState["negativeZero"] = math.Copysign(0, -1)
	want, err := canonicalJSON(authority.CanonicalPayload())
	if err != nil {
		t.Fatal(err)
	}
	digest := authorityDigestForTest(t, authority)
	for _, event := range []string{"decision", "admission"} {
		t.Run(event, func(t *testing.T) {
			tx := &fakeAuditTx{}
			repository, err := NewAuditRepository(tx)
			if err != nil {
				t.Fatal(err)
			}
			switch event {
			case "decision":
				err = repository.RecordDecision(context.Background(), authority.Authorization, &authority)
			case "admission":
				err = repository.RecordAdmission(context.Background(), authority, AuthorityAdmissionDecision{
					AuthorityDigest: digest,
					Decision:        "ADMIT",
				})
			}
			if err != nil {
				t.Fatal(err)
			}
			if tx.calls != 1 {
				t.Fatalf("expected one audit insert, got %d", tx.calls)
			}
			var payload map[string]any
			decoder := json.NewDecoder(strings.NewReader(tx.args[3].(string)))
			decoder.UseNumber()
			if err := decoder.Decode(&payload); err != nil {
				t.Fatal(err)
			}
			envelope, ok := payload["authorityEnvelope"].(map[string]any)
			if !ok || envelope["authorityDigest"] != digest {
				t.Fatalf("missing or inconsistent authority envelope: %#v", payload)
			}
			delete(envelope, "authorityDigest")
			delete(envelope, "digestAlgorithm")
			got, err := canonicalJSON(envelope)
			if err != nil {
				t.Fatal(err)
			}
			if string(got) != string(want) {
				t.Fatalf("persisted canonical envelope differs: got %s want %s", got, want)
			}
		})
	}
}


func TestRecordAdmissionPreservesCanonicalDiffValues(t *testing.T) {
	tx := &fakeAuditTx{}
	repository, err := NewAuditRepository(tx)
	if err != nil {
		t.Fatal(err)
	}
	authority := referenceAuthority()
	admission := AuthorityAdmissionDecision{
		AuthorityDigest:        authorityDigestForTest(t, authority),
		Decision:               "DENY",
		ReasonCode:             "AUTHORITY_STATE_DRIFT",
		CurrentState:           map[string]any{},
		CurrentResourceVersion: "resource:v1",
		RequestedWrite:         map[string]any{},
		StateDiff: map[string]DiffValue{
			"ratio": {Expected: float64(1e-5), Current: math.Copysign(0, -1)},
		},
		WriteDiff: map[string]DiffValue{
			"limit": {Expected: float64(1e16), Current: float64(1e-4)},
		},
		AdmissionVersion: AuthorityAdmissionVersion,
		AdmittedAt:       "2026-09-30T00:00:02+00:00",
	}

	if err := repository.RecordAdmission(context.Background(), authority, admission); err != nil {
		t.Fatal(err)
	}
	var payload map[string]any
	decoder := json.NewDecoder(strings.NewReader(tx.args[3].(string)))
	decoder.UseNumber()
	if err := decoder.Decode(&payload); err != nil {
		t.Fatal(err)
	}
	persisted, ok := payload["admission"].(map[string]any)
	if !ok {
		t.Fatalf("missing persisted admission: %#v", payload)
	}
	got, err := canonicalJSON(persisted)
	if err != nil {
		t.Fatal(err)
	}
	want, err := canonicalJSON(admission.Payload())
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != string(want) {
		t.Fatalf("persisted admission differs from canonical payload: got %s want %s", got, want)
	}
}
