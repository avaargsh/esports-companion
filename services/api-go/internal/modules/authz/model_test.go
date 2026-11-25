package authz

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"math"
	"reflect"
	"testing"
	"time"
)

func referenceDecision() AuthorizationDecision {
	return AuthorizationDecision{
		ActorUserID:         "00000000-0000-0000-0000-000000000101",
		ActorRoles:          []string{"USER", "PLATFORM"},
		Action:              "WITHDRAWAL_COMPLETE",
		ResourceType:        "WITHDRAWAL",
		ResourceID:          "00000000-0000-0000-0000-000000000201",
		Scope:               "PLATFORM",
		Decision:            "ALLOW",
		ReasonCode:          "PLATFORM_ROLE",
		PolicyVersion:       PolicyVersion,
		SessionID:           "00000000-0000-0000-0000-000000000301",
		RequestID:           "request-1",
		BusinessEvidenceRef: "WITHDRAWAL:00000000-0000-0000-0000-000000000201",
		OccurredAt:          "2026-09-30T00:00:00+00:00",
	}
}

func referenceAuthority() AuthorityEnvelope {
	return AuthorityEnvelope{
		Authorization: referenceDecision(),
		ExpectedState: map[string]any{
			"withdrawalStatus":    "PENDING",
			"walletVersion":       7,
			"walletFrozenBalance": 2500,
		},
		BoundedWrite: map[string]any{
			"operation":        "WITHDRAWAL_COMPLETE",
			"providerTxnId":    "payout-1",
			"withdrawalStatus": "COMPLETED",
		},
		ResourceVersion: "withdrawal:00000000-0000-0000-0000-000000000201:status=PENDING;wallet:00000000-0000-0000-0000-000000000401:v7",
		IssuedAt:        "2026-09-30T00:00:01+00:00",
	}
}

func TestAuthorityDigestMatchesPythonReference(t *testing.T) {
	digest, err := referenceAuthority().Digest()
	if err != nil {
		t.Fatal(err)
	}
	const expected = "62a387460981323471c416c283c4aab2ce0dcc7085294c0ec2749dc50664ce1c"
	if digest != expected {
		t.Fatalf("digest mismatch: got %s want %s", digest, expected)
	}
}

func TestRequireOwnerCarriesEvidence(t *testing.T) {
	decision, err := RequireOwner(OwnerPolicyInput{
		ActorUserID:         "user-1",
		ActorRoles:          []string{"USER", "PLAYER"},
		OwnerUserID:         "user-1",
		Action:              "WITHDRAWAL_LIST",
		ResourceType:        "WITHDRAWAL",
		ResourceID:          "collection",
		SessionID:           "session-1",
		RequestID:           "request-owner-1",
		BusinessEvidenceRef: "WITHDRAWAL:collection",
		OccurredAt:          "2026-09-30T00:00:00+00:00",
	})
	if err != nil {
		t.Fatal(err)
	}
	if decision.Decision != "ALLOW" || decision.ReasonCode != "OWNER_MATCH" {
		t.Fatalf("unexpected decision: %#v", decision)
	}
	payload := decision.Payload()
	if payload["requestId"] != "request-owner-1" || payload["policyVersion"] != PolicyVersion {
		t.Fatalf("missing evidence context: %#v", payload)
	}
}

func TestRequireOwnerDenialIsStructured(t *testing.T) {
	_, err := RequireOwner(OwnerPolicyInput{
		ActorUserID:  "user-1",
		ActorRoles:   []string{"USER"},
		OwnerUserID:  "user-2",
		Action:       "WALLET_READ",
		ResourceType: "WALLET",
		ResourceID:   "wallet-1",
		DenialCode:   "WALLET_ACCESS_DENIED",
	})
	var denied *ResourceAuthorizationDenied
	if !errors.As(err, &denied) {
		t.Fatalf("expected ResourceAuthorizationDenied, got %v", err)
	}
	if denied.Decision.Decision != "DENY" || denied.Decision.ReasonCode != "WALLET_ACCESS_DENIED" {
		t.Fatalf("unexpected denial: %#v", denied.Decision)
	}
}

func TestRequirePlatform(t *testing.T) {
	decision, err := RequirePlatform(PlatformPolicyInput{
		ActorUserID:  "admin-1",
		ActorRoles:   []string{"USER", "PLATFORM"},
		Action:       "PLAYER_APPROVE",
		ResourceType: "PLAYER_PROFILE",
		ResourceID:   "player-1",
	})
	if err != nil {
		t.Fatal(err)
	}
	if decision.Scope != "PLATFORM" || decision.ReasonCode != "PLATFORM_ROLE" {
		t.Fatalf("unexpected platform decision: %#v", decision)
	}

	_, err = RequirePlatform(PlatformPolicyInput{
		ActorUserID:  "user-1",
		ActorRoles:   []string{"USER"},
		Action:       "PLAYER_APPROVE",
		ResourceType: "PLAYER_PROFILE",
		ResourceID:   "player-1",
	})
	var denied *ResourceAuthorizationDenied
	if !errors.As(err, &denied) || denied.Decision.ReasonCode != "PLATFORM_REQUIRED" {
		t.Fatalf("unexpected platform denial: %v", err)
	}
}

func TestAuthorityAdmissionExactMatch(t *testing.T) {
	authority := referenceAuthority()
	admission, err := Admit(
		authority,
		authority.ExpectedState,
		authority.ResourceVersion,
		authority.BoundedWrite,
	)
	if err != nil {
		t.Fatal(err)
	}
	if admission.Decision != "ADMIT" || admission.ReasonCode != "AUTHORITY_EXACT_MATCH" {
		t.Fatalf("unexpected admission: %#v", admission)
	}
	if len(admission.StateDiff) != 0 || len(admission.WriteDiff) != 0 {
		t.Fatalf("expected empty diffs: %#v", admission)
	}
	firstPayload := admission.Payload()
	secondPayload := admission.Payload()
	if !reflect.DeepEqual(firstPayload, secondPayload) {
		t.Fatalf("admission payload changed between reads: first=%#v second=%#v", firstPayload, secondPayload)
	}
}

func TestAuthorityAdmissionDeniesStateDrift(t *testing.T) {
	authority := referenceAuthority()
	current := cloneMap(authority.ExpectedState)
	current["walletVersion"] = 8

	_, err := Admit(
		authority,
		current,
		"withdrawal:201:status=PENDING;wallet:401:v8",
		authority.BoundedWrite,
	)
	var denied *AuthorityAdmissionDenied
	if !errors.As(err, &denied) {
		t.Fatalf("expected AuthorityAdmissionDenied, got %v", err)
	}
	if denied.Admission.ReasonCode != "AUTHORITY_STATE_DRIFT" {
		t.Fatalf("unexpected denial: %#v", denied.Admission)
	}
	diff := denied.Admission.StateDiff["walletVersion"]
	if diff.Expected != 7 || diff.Current != 8 {
		t.Fatalf("unexpected state diff: %#v", diff)
	}
}

func TestAuthorityAdmissionDeniesWriteMismatchFirst(t *testing.T) {
	authority := referenceAuthority()
	write := cloneMap(authority.BoundedWrite)
	write["providerTxnId"] = "payout-2"

	_, err := Admit(authority, authority.ExpectedState, authority.ResourceVersion, write)
	var denied *AuthorityAdmissionDenied
	if !errors.As(err, &denied) {
		t.Fatalf("expected AuthorityAdmissionDenied, got %v", err)
	}
	if denied.Admission.ReasonCode != "AUTHORITY_BOUNDED_WRITE_MISMATCH" {
		t.Fatalf("unexpected denial: %#v", denied.Admission)
	}
}

func TestAuthorityPayloadDigestMatchesReturnedSnapshot(t *testing.T) {
	decision, err := RequireOwner(OwnerPolicyInput{
		ActorUserID:  "00000000-0000-0000-0000-000000000101",
		ActorRoles:   []string{"USER"},
		OwnerUserID:  "00000000-0000-0000-0000-000000000101",
		Action:       "ORDER_READ",
		ResourceType: "ORDER",
		ResourceID:   "00000000-0000-0000-0000-000000000201",
	})
	if err != nil {
		t.Fatal(err)
	}

	authority := NewAuthorityEnvelope(AuthorityEnvelopeInput{
		Authorization:   decision,
		ExpectedState:   map[string]any{"status": "MATCHING"},
		BoundedWrite:    map[string]any{"operation": "ORDER_READ"},
		ResourceVersion: "order:00000000-0000-0000-0000-000000000201:v1",
	})

	first, err := authority.Payload()
	if err != nil {
		t.Fatal(err)
	}
	second, err := authority.Payload()
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(first, second) {
		t.Fatalf("authority payload changed between reads: first=%#v second=%#v", first, second)
	}

	digest, err := authority.Digest()
	if err != nil {
		t.Fatal(err)
	}
	if first["authorityDigest"] != digest {
		t.Fatalf("payload digest does not match stable envelope digest: payload=%v digest=%s", first["authorityDigest"], digest)
	}

	admission, err := Admit(authority, authority.ExpectedState, authority.ResourceVersion, authority.BoundedWrite)
	if err != nil {
		t.Fatal(err)
	}
	if admission.AuthorityDigest != digest {
		t.Fatalf("admission digest changed: got %s want %s", admission.AuthorityDigest, digest)
	}

	delete(first, "digestAlgorithm")
	delete(first, "authorityDigest")
	canonical, err := json.Marshal(first)
	if err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256(canonical)
	if got := hex.EncodeToString(sum[:]); digest != got {
		t.Fatalf("payload digest does not match its serialized snapshot: got %s want %s", digest, got)
	}
}

func TestAuthorityAdmissionMatchesPythonNumericEquality(t *testing.T) {
	authority := referenceAuthority()
	authority.ExpectedState["metadata"] = map[string]any{
		"version": int64(7),
		"counts":  []any{int64(2), int64(3)},
	}
	currentState := cloneMap(authority.ExpectedState)
	currentState["walletVersion"] = float64(7)
	currentState["walletFrozenBalance"] = float64(2500)
	currentState["metadata"] = map[string]any{
		"version": float64(7),
		"counts":  []any{float64(2), float64(3)},
	}

	admission, err := Admit(authority, currentState, authority.ResourceVersion, authority.BoundedWrite)
	if err != nil {
		t.Fatalf("JSON-equivalent numeric values should admit: %v", err)
	}
	if admission.Decision != "ADMIT" || len(admission.StateDiff) != 0 {
		t.Fatalf("unexpected admission for equivalent JSON values: %#v", admission)
	}
}

func TestRequireOwnerRejectsEmptyActorID(t *testing.T) {
	_, err := RequireOwner(OwnerPolicyInput{
		ActorUserID:  "",
		OwnerUserID:  "",
		Action:       "WALLET_READ",
		ResourceType: "WALLET",
		ResourceID:   "wallet-1",
	})
	var denied *ResourceAuthorizationDenied
	if !errors.As(err, &denied) || denied.Decision.ReasonCode != "ACTOR_REQUIRED" {
		t.Fatalf("expected fail-closed actor validation, got %v", err)
	}
}

func TestRequirePlatformRejectsEmptyActorID(t *testing.T) {
	_, err := RequirePlatform(PlatformPolicyInput{
		ActorUserID:  "",
		ActorRoles:   []string{"PLATFORM"},
		Action:       "PLAYER_APPROVE",
		ResourceType: "PLAYER_PROFILE",
		ResourceID:   "player-1",
	})
	var denied *ResourceAuthorizationDenied
	if !errors.As(err, &denied) || denied.Decision.ReasonCode != "ACTOR_REQUIRED" {
		t.Fatalf("expected fail-closed actor validation, got %v", err)
	}
}

func TestAuthorityEnvelopeRejectsMissingRuntimeDefaults(t *testing.T) {
	authority := referenceAuthority()
	authority.IssuedAt = ""
	if _, err := authority.Digest(); err == nil {
		t.Fatal("expected missing issuedAt to fail closed")
	}

	authority = referenceAuthority()
	authority.Authorization.OccurredAt = ""
	if _, err := authority.Payload(); err == nil {
		t.Fatal("expected missing authorization occurredAt to fail closed")
	}
}

func TestCanonicalJSONMatchesPythonUnicodeContract(t *testing.T) {
	value := map[string]any{
		"literal": "\\\\u2028",
		"note":    "<ready>&\u2028中",
	}
	encoded, err := canonicalJSON(value)
	if err != nil {
		t.Fatal(err)
	}
	expected := "{\"literal\":\"\\\\\\\\u2028\",\"note\":\"<ready>&" + "\u2028" + "中\"}"
	if string(encoded) != expected {
		t.Fatalf("canonical JSON mismatch: got %q want %q", string(encoded), expected)
	}
}

func TestAuthorityDigestMatchesPythonUnicodeGoldenVector(t *testing.T) {
	authority := NewAuthorityEnvelope(AuthorityEnvelopeInput{
		Authorization: AuthorizationDecision{
			ActorUserID:         "user-1",
			ActorRoles:          []string{"USER"},
			Action:              "ORDER_READ",
			ResourceType:        "ORDER",
			ResourceID:          "order-1",
			Scope:               "OWNER",
			Decision:            "ALLOW",
			ReasonCode:          "OWNER_MATCH",
			PolicyVersion:       PolicyVersion,
			RequestID:           "req-1",
			BusinessEvidenceRef: "<order>&\u2028中",
			OccurredAt:          "2026-11-24T08:00:00+00:00",
		},
		ExpectedState:   map[string]any{"note": "<ready>&\u2028中"},
		BoundedWrite:    map[string]any{"operation": "ORDER_READ"},
		ResourceVersion: "order:1:v1",
		IssuedAt:        "2026-11-24T08:00:01+00:00",
	})
	digest, err := authority.Digest()
	if err != nil {
		t.Fatal(err)
	}
	const expected = "eb0c71e4b5f72a5c6a9adea249349d6ad402089f2a995500575d234b459b08ed"
	if digest != expected {
		t.Fatalf("Unicode/HTML digest mismatch: got %s want %s", digest, expected)
	}
}

func TestDiffMatchesPythonNumericAndMissingNullSemantics(t *testing.T) {
	got := diff(
		map[string]any{
			"walletVersion": 7,
			"optional":      nil,
			"nested":        map[string]any{"amount": int64(2500)},
		},
		map[string]any{
			"walletVersion": float64(7),
			"nested":        map[string]any{"amount": json.Number("2500")},
		},
	)
	if len(got) != 0 {
		t.Fatalf("Python-equivalent state values should not drift: %#v", got)
	}
}

func TestAuthorizationDecisionPayloadUsesEmptyRolesArray(t *testing.T) {
	decision := AuthorizationDecision{
		ActorUserID:  "user-1",
		Action:       "ORDER_READ",
		ResourceType: "ORDER",
		ResourceID:   "order-1",
		Scope:        "OWNER",
		Decision:     "ALLOW",
		ReasonCode:   "OWNER_MATCH",
		OccurredAt:   "2026-11-24T08:00:00+00:00",
	}
	roles, ok := decision.Payload()["actorRoles"].([]string)
	if !ok || roles == nil || len(roles) != 0 {
		t.Fatalf("expected an empty JSON array for actorRoles, got %#v", decision.Payload()["actorRoles"])
	}
}

func TestUTCISOUsesPythonMicrosecondPrecision(t *testing.T) {
	value := time.Date(2026, 11, 24, 8, 0, 0, 123456789, time.UTC)
	const expected = "2026-11-24T08:00:00.123456+00:00"
	if got := utcISO(value); got != expected {
		t.Fatalf("timestamp precision mismatch: got %s want %s", got, expected)
	}
}

func TestCanonicalJSONMatchesPythonFloatFormatting(t *testing.T) {
	value := map[string]any{
		"fixedLarge":      float64(1e15),
		"fixedSmall":      float64(1e-4),
		"negativeZero":    math.Copysign(0, -1),
		"scientificLarge": float64(1e16),
		"scientificSmall": float64(1e-5),
		"nested": []any{
			float64(1.0),
			map[string]any{"small": float64(1e-5)},
		},
	}
	encoded, err := canonicalJSON(value)
	if err != nil {
		t.Fatal(err)
	}
	const expected = `{"fixedLarge":1000000000000000.0,"fixedSmall":0.0001,"negativeZero":-0.0,"nested":[1.0,{"small":1e-05}],"scientificLarge":1e+16,"scientificSmall":1e-05}`
	if string(encoded) != expected {
		t.Fatalf("Python float JSON mismatch: got %s want %s", encoded, expected)
	}
}

func TestDiffMatchesPythonBooleanNumericEquality(t *testing.T) {
	got := diff(
		map[string]any{"enabled": true, "disabled": false},
		map[string]any{"enabled": int64(1), "disabled": float64(0)},
	)
	if len(got) != 0 {
		t.Fatalf("Python bool/numeric-equivalent values should not drift: %#v", got)
	}
}


func TestAuthorityAdmissionPayloadCanonicalizesNestedDiffValues(t *testing.T) {
	admission := AuthorityAdmissionDecision{
		AuthorityDigest:        "digest",
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

	encoded, err := canonicalJSON(admission.Payload())
	if err != nil {
		t.Fatal(err)
	}
	const expected = `{"admissionVersion":"authority-admission.v1","admittedAt":"2026-09-30T00:00:02+00:00","authorityDigest":"digest","currentResourceVersion":"resource:v1","currentState":{},"decision":"DENY","reasonCode":"AUTHORITY_STATE_DRIFT","requestedWrite":{},"stateDiff":{"ratio":{"current":-0.0,"expected":1e-05}},"writeDiff":{"limit":{"current":0.0001,"expected":1e+16}}}`
	if string(encoded) != expected {
		t.Fatalf("Python-compatible admission JSON mismatch: got %s want %s", encoded, expected)
	}
}
