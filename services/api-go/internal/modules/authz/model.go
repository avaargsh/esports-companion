package authz

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"reflect"
	"sort"
	"time"
)

const (
	PolicyVersion             = "resource-authz.v2"
	AuthorityEnvelopeVersion  = "authority-envelope.v1"
	AuthorityAdmissionVersion = "authority-admission.v1"
)

type AuthorizationDecision struct {
	ActorUserID        string
	ActorRoles         []string
	Action             string
	ResourceType       string
	ResourceID         string
	Scope              string
	Decision           string
	ReasonCode         string
	PolicyVersion      string
	SessionID          string
	RequestID          string
	BusinessEvidenceRef string
	OccurredAt         string
}

func (d AuthorizationDecision) Payload() map[string]any {
	policyVersion := d.PolicyVersion
	if policyVersion == "" {
		policyVersion = PolicyVersion
	}
	occurredAt := d.OccurredAt
	if occurredAt == "" {
		occurredAt = utcISO(time.Now())
	}
	return map[string]any{
		"actorUserId":        d.ActorUserID,
		"actorRoles":         append([]string(nil), d.ActorRoles...),
		"action":             d.Action,
		"resourceType":       d.ResourceType,
		"resourceId":         d.ResourceID,
		"scope":              d.Scope,
		"decision":           d.Decision,
		"reasonCode":         d.ReasonCode,
		"policyVersion":      policyVersion,
		"sessionId":          nullableString(d.SessionID),
		"requestId":          nullableString(d.RequestID),
		"businessEvidenceRef": nullableString(d.BusinessEvidenceRef),
		"occurredAt":         occurredAt,
	}
}

type ResourceAuthorizationDenied struct {
	Decision AuthorizationDecision
}

func (e *ResourceAuthorizationDenied) Error() string {
	return e.Decision.ReasonCode
}

type OwnerPolicyInput struct {
	ActorUserID         string
	ActorRoles          []string
	OwnerUserID         string
	Action              string
	ResourceType        string
	ResourceID          string
	DenialCode          string
	SessionID           string
	RequestID           string
	BusinessEvidenceRef string
	OccurredAt          string
}

func RequireOwner(input OwnerPolicyInput) (AuthorizationDecision, error) {
	denialCode := input.DenialCode
	if denialCode == "" {
		denialCode = "RESOURCE_NOT_OWNED"
	}
	decision := AuthorizationDecision{
		ActorUserID:         input.ActorUserID,
		ActorRoles:          append([]string(nil), input.ActorRoles...),
		Action:              input.Action,
		ResourceType:        input.ResourceType,
		ResourceID:          input.ResourceID,
		Scope:               "OWNER",
		PolicyVersion:       PolicyVersion,
		SessionID:           input.SessionID,
		RequestID:           input.RequestID,
		BusinessEvidenceRef: input.BusinessEvidenceRef,
		OccurredAt:          input.OccurredAt,
	}
	if input.ActorUserID != input.OwnerUserID {
		decision.Decision = "DENY"
		decision.ReasonCode = denialCode
		return AuthorizationDecision{}, &ResourceAuthorizationDenied{Decision: decision}
	}
	decision.Decision = "ALLOW"
	decision.ReasonCode = "OWNER_MATCH"
	return decision, nil
}

type PlatformPolicyInput struct {
	ActorUserID         string
	ActorRoles          []string
	Action              string
	ResourceType        string
	ResourceID          string
	SessionID           string
	RequestID           string
	BusinessEvidenceRef string
	OccurredAt          string
}

func RequirePlatform(input PlatformPolicyInput) (AuthorizationDecision, error) {
	decision := AuthorizationDecision{
		ActorUserID:         input.ActorUserID,
		ActorRoles:          append([]string(nil), input.ActorRoles...),
		Action:              input.Action,
		ResourceType:        input.ResourceType,
		ResourceID:          input.ResourceID,
		Scope:               "PLATFORM",
		PolicyVersion:       PolicyVersion,
		SessionID:           input.SessionID,
		RequestID:           input.RequestID,
		BusinessEvidenceRef: input.BusinessEvidenceRef,
		OccurredAt:          input.OccurredAt,
	}
	if !contains(input.ActorRoles, "PLATFORM") {
		decision.Decision = "DENY"
		decision.ReasonCode = "PLATFORM_REQUIRED"
		return AuthorizationDecision{}, &ResourceAuthorizationDenied{Decision: decision}
	}
	decision.Decision = "ALLOW"
	decision.ReasonCode = "PLATFORM_ROLE"
	return decision, nil
}

type AuthorityEnvelope struct {
	Authorization   AuthorizationDecision
	ExpectedState   map[string]any
	BoundedWrite    map[string]any
	ResourceVersion string
	ApprovalID      string
	EnvelopeVersion string
	IssuedAt        string
}

func (a AuthorityEnvelope) CanonicalPayload() map[string]any {
	version := a.EnvelopeVersion
	if version == "" {
		version = AuthorityEnvelopeVersion
	}
	issuedAt := a.IssuedAt
	if issuedAt == "" {
		issuedAt = utcISO(time.Now())
	}
	return map[string]any{
		"envelopeVersion": version,
		"authorization":   a.Authorization.Payload(),
		"expectedState":   cloneMap(a.ExpectedState),
		"boundedWrite":    cloneMap(a.BoundedWrite),
		"resourceVersion": a.ResourceVersion,
		"approvalId":      nullableString(a.ApprovalID),
		"issuedAt":        issuedAt,
	}
}

func (a AuthorityEnvelope) Digest() (string, error) {
	canonical, err := json.Marshal(a.CanonicalPayload())
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(canonical)
	return hex.EncodeToString(sum[:]), nil
}

func (a AuthorityEnvelope) Payload() (map[string]any, error) {
	payload := a.CanonicalPayload()
	digest, err := a.Digest()
	if err != nil {
		return nil, err
	}
	payload["digestAlgorithm"] = "sha256"
	payload["authorityDigest"] = digest
	return payload, nil
}

type DiffValue struct {
	Expected any `json:"expected"`
	Current  any `json:"current"`
}

type AuthorityAdmissionDecision struct {
	AuthorityDigest       string
	Decision              string
	ReasonCode            string
	CurrentState          map[string]any
	CurrentResourceVersion string
	RequestedWrite        map[string]any
	StateDiff             map[string]DiffValue
	WriteDiff             map[string]DiffValue
	AdmissionVersion      string
	AdmittedAt            string
}

func (d AuthorityAdmissionDecision) Payload() map[string]any {
	version := d.AdmissionVersion
	if version == "" {
		version = AuthorityAdmissionVersion
	}
	admittedAt := d.AdmittedAt
	if admittedAt == "" {
		admittedAt = utcISO(time.Now())
	}
	return map[string]any{
		"admissionVersion":       version,
		"authorityDigest":        d.AuthorityDigest,
		"decision":               d.Decision,
		"reasonCode":             d.ReasonCode,
		"currentState":           cloneMap(d.CurrentState),
		"currentResourceVersion": d.CurrentResourceVersion,
		"requestedWrite":         cloneMap(d.RequestedWrite),
		"stateDiff":              d.StateDiff,
		"writeDiff":              d.WriteDiff,
		"admittedAt":             admittedAt,
	}
}

type AuthorityAdmissionDenied struct {
	Authority AuthorityEnvelope
	Admission AuthorityAdmissionDecision
}

func (e *AuthorityAdmissionDenied) Error() string {
	return e.Admission.ReasonCode
}

func Admit(
	authority AuthorityEnvelope,
	currentState map[string]any,
	currentResourceVersion string,
	requestedWrite map[string]any,
) (AuthorityAdmissionDecision, error) {
	digest, err := authority.Digest()
	if err != nil {
		return AuthorityAdmissionDecision{}, err
	}
	stateDiff := diff(authority.ExpectedState, currentState)
	writeDiff := diff(authority.BoundedWrite, requestedWrite)
	base := AuthorityAdmissionDecision{
		AuthorityDigest:        digest,
		CurrentState:           cloneMap(currentState),
		CurrentResourceVersion: currentResourceVersion,
		RequestedWrite:         cloneMap(requestedWrite),
		StateDiff:              stateDiff,
		WriteDiff:              writeDiff,
		AdmissionVersion:       AuthorityAdmissionVersion,
		AdmittedAt:             utcISO(time.Now()),
	}

	if len(writeDiff) > 0 {
		base.Decision = "DENY"
		base.ReasonCode = "AUTHORITY_BOUNDED_WRITE_MISMATCH"
		return AuthorityAdmissionDecision{}, &AuthorityAdmissionDenied{
			Authority: authority,
			Admission: base,
		}
	}
	if len(stateDiff) > 0 || authority.ResourceVersion != currentResourceVersion {
		base.Decision = "DENY"
		base.ReasonCode = "AUTHORITY_STATE_DRIFT"
		return AuthorityAdmissionDecision{}, &AuthorityAdmissionDenied{
			Authority: authority,
			Admission: base,
		}
	}

	base.Decision = "ADMIT"
	base.ReasonCode = "AUTHORITY_EXACT_MATCH"
	return base, nil
}

func diff(expected, current map[string]any) map[string]DiffValue {
	keys := map[string]struct{}{}
	for key := range expected {
		keys[key] = struct{}{}
	}
	for key := range current {
		keys[key] = struct{}{}
	}
	ordered := make([]string, 0, len(keys))
	for key := range keys {
		ordered = append(ordered, key)
	}
	sort.Strings(ordered)

	result := map[string]DiffValue{}
	for _, key := range ordered {
		expectedValue, expectedOK := expected[key]
		currentValue, currentOK := current[key]
		if expectedOK != currentOK || !reflect.DeepEqual(expectedValue, currentValue) {
			result[key] = DiffValue{Expected: expectedValue, Current: currentValue}
		}
	}
	return result
}

func cloneMap(value map[string]any) map[string]any {
	if value == nil {
		return map[string]any{}
	}
	cloned := make(map[string]any, len(value))
	for key, item := range value {
		cloned[key] = item
	}
	return cloned
}

func nullableString(value string) any {
	if value == "" {
		return nil
	}
	return value
}

func contains(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}

func utcISO(value time.Time) string {
	return value.UTC().Format("2006-01-02T15:04:05.999999999+00:00")
}

