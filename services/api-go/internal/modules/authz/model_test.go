package authz

import (
	"errors"
	"testing"
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
