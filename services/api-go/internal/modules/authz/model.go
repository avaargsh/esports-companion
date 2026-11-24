package authz

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"math"
	"math/big"
	"reflect"
	"sort"
	"strconv"
	"strings"
	"time"
)

const (
	PolicyVersion             = "resource-authz.v2"
	AuthorityEnvelopeVersion  = "authority-envelope.v1"
	AuthorityAdmissionVersion = "authority-admission.v1"
)

type AuthorizationDecision struct {
	ActorUserID         string
	ActorRoles          []string
	Action              string
	ResourceType        string
	ResourceID          string
	Scope               string
	Decision            string
	ReasonCode          string
	PolicyVersion       string
	SessionID           string
	RequestID           string
	BusinessEvidenceRef string
	OccurredAt          string
}

func (d AuthorizationDecision) Payload() map[string]any {
	policyVersion := d.PolicyVersion
	if policyVersion == "" {
		policyVersion = PolicyVersion
	}
	occurredAt := d.OccurredAt
	return map[string]any{
		"actorUserId":         d.ActorUserID,
		"actorRoles":          append([]string{}, d.ActorRoles...),
		"action":              d.Action,
		"resourceType":        d.ResourceType,
		"resourceId":          d.ResourceID,
		"scope":               d.Scope,
		"decision":            d.Decision,
		"reasonCode":          d.ReasonCode,
		"policyVersion":       policyVersion,
		"sessionId":           nullableString(d.SessionID),
		"requestId":           nullableString(d.RequestID),
		"businessEvidenceRef": nullableString(d.BusinessEvidenceRef),
		"occurredAt":          occurredAt,
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
	occurredAt := input.OccurredAt
	if occurredAt == "" {
		occurredAt = utcISO(time.Now())
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
		OccurredAt:          occurredAt,
	}
	if strings.TrimSpace(input.ActorUserID) == "" {
		decision.Decision = "DENY"
		decision.ReasonCode = "ACTOR_REQUIRED"
		return AuthorizationDecision{}, &ResourceAuthorizationDenied{Decision: decision}
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
	occurredAt := input.OccurredAt
	if occurredAt == "" {
		occurredAt = utcISO(time.Now())
	}
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
		OccurredAt:          occurredAt,
	}
	if strings.TrimSpace(input.ActorUserID) == "" {
		decision.Decision = "DENY"
		decision.ReasonCode = "ACTOR_REQUIRED"
		return AuthorizationDecision{}, &ResourceAuthorizationDenied{Decision: decision}
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

type AuthorityEnvelopeInput struct {
	Authorization   AuthorizationDecision
	ExpectedState   map[string]any
	BoundedWrite    map[string]any
	ResourceVersion string
	ApprovalID      string
	EnvelopeVersion string
	IssuedAt        string
}

// NewAuthorityEnvelope captures Python's dataclass default-factory semantics:
// generated timestamps are assigned once when the envelope is created, not
// regenerated every time its payload or digest is read.
func NewAuthorityEnvelope(input AuthorityEnvelopeInput) AuthorityEnvelope {
	authorization := input.Authorization
	if authorization.OccurredAt == "" {
		authorization.OccurredAt = utcISO(time.Now())
	}
	envelopeVersion := input.EnvelopeVersion
	if envelopeVersion == "" {
		envelopeVersion = AuthorityEnvelopeVersion
	}
	issuedAt := input.IssuedAt
	if issuedAt == "" {
		issuedAt = utcISO(time.Now())
	}
	return AuthorityEnvelope{
		Authorization:   authorization,
		ExpectedState:   cloneMap(input.ExpectedState),
		BoundedWrite:    cloneMap(input.BoundedWrite),
		ResourceVersion: input.ResourceVersion,
		ApprovalID:      input.ApprovalID,
		EnvelopeVersion: envelopeVersion,
		IssuedAt:        issuedAt,
	}
}

func (a AuthorityEnvelope) CanonicalPayload() map[string]any {
	version := a.EnvelopeVersion
	if version == "" {
		version = AuthorityEnvelopeVersion
	}
	return map[string]any{
		"envelopeVersion": version,
		"authorization":   a.Authorization.Payload(),
		"expectedState":   cloneMap(a.ExpectedState),
		"boundedWrite":    cloneMap(a.BoundedWrite),
		"resourceVersion": a.ResourceVersion,
		"approvalId":      nullableString(a.ApprovalID),
		"issuedAt":        a.IssuedAt,
	}
}

func (a AuthorityEnvelope) validate() error {
	if strings.TrimSpace(a.IssuedAt) == "" {
		return errors.New("authority envelope issuedAt is required; use NewAuthorityEnvelope")
	}
	if strings.TrimSpace(a.Authorization.OccurredAt) == "" {
		return errors.New("authority authorization occurredAt is required; use NewAuthorityEnvelope")
	}
	return nil
}

func (a AuthorityEnvelope) Digest() (string, error) {
	if err := a.validate(); err != nil {
		return "", err
	}
	canonical, err := canonicalJSON(a.CanonicalPayload())
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(canonical)
	return hex.EncodeToString(sum[:]), nil
}

func (a AuthorityEnvelope) Payload() (map[string]any, error) {
	if err := a.validate(); err != nil {
		return nil, err
	}
	payload := a.CanonicalPayload()
	canonical, err := canonicalJSON(payload)
	if err != nil {
		return nil, err
	}
	sum := sha256.Sum256(canonical)
	payload["digestAlgorithm"] = "sha256"
	payload["authorityDigest"] = hex.EncodeToString(sum[:])
	return payload, nil
}

type DiffValue struct {
	Expected any `json:"expected"`
	Current  any `json:"current"`
}

type AuthorityAdmissionDecision struct {
	AuthorityDigest        string
	Decision               string
	ReasonCode             string
	CurrentState           map[string]any
	CurrentResourceVersion string
	RequestedWrite         map[string]any
	StateDiff              map[string]DiffValue
	WriteDiff              map[string]DiffValue
	AdmissionVersion       string
	AdmittedAt             string
}

func (d AuthorityAdmissionDecision) Payload() map[string]any {
	version := d.AdmissionVersion
	if version == "" {
		version = AuthorityAdmissionVersion
	}
	admittedAt := d.AdmittedAt
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
		expectedValue := expected[key]
		currentValue := current[key]
		// Match Python dict.get/equality semantics: absent and null compare
		// equal, and numerics compare by value even when Go types differ.
		if !valuesEqual(expectedValue, currentValue) {
			result[key] = DiffValue{Expected: expectedValue, Current: currentValue}
		}
	}
	return result
}

func valuesEqual(left, right any) bool {
	if reflect.DeepEqual(left, right) {
		return true
	}
	if leftNumber, ok := numericRat(left); ok {
		rightNumber, rightOK := numericRat(right)
		return rightOK && leftNumber.Cmp(rightNumber) == 0
	}

	leftValue := reflect.ValueOf(left)
	rightValue := reflect.ValueOf(right)
	if !leftValue.IsValid() || !rightValue.IsValid() {
		return !leftValue.IsValid() && !rightValue.IsValid()
	}

	if leftValue.Kind() == reflect.Map && rightValue.Kind() == reflect.Map {
		if leftValue.Type().Key().Kind() != reflect.String ||
			rightValue.Type().Key().Kind() != reflect.String ||
			leftValue.IsNil() != rightValue.IsNil() ||
			leftValue.Len() != rightValue.Len() {
			return false
		}
		for _, key := range leftValue.MapKeys() {
			rightKey := reflect.ValueOf(key.String()).Convert(rightValue.Type().Key())
			rightItem := rightValue.MapIndex(rightKey)
			if !rightItem.IsValid() ||
				!valuesEqual(leftValue.MapIndex(key).Interface(), rightItem.Interface()) {
				return false
			}
		}
		return true
	}

	if leftValue.Kind() == reflect.Slice && rightValue.Kind() == reflect.Slice {
		if leftValue.IsNil() != rightValue.IsNil() || leftValue.Len() != rightValue.Len() {
			return false
		}
		for index := 0; index < leftValue.Len(); index++ {
			if !valuesEqual(leftValue.Index(index).Interface(), rightValue.Index(index).Interface()) {
				return false
			}
		}
		return true
	}
	return false
}

func numericRat(value any) (*big.Rat, bool) {
	if number, ok := value.(json.Number); ok {
		return new(big.Rat).SetString(number.String())
	}
	reflected := reflect.ValueOf(value)
	if !reflected.IsValid() {
		return nil, false
	}
	switch reflected.Kind() {
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		return new(big.Rat).SetInt64(reflected.Int()), true
	case reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64, reflect.Uintptr:
		return new(big.Rat).SetInt(new(big.Int).SetUint64(reflected.Uint())), true
	case reflect.Bool:
		if reflected.Bool() {
			return new(big.Rat).SetInt64(1), true
		}
		return new(big.Rat).SetInt64(0), true
	case reflect.Float32, reflect.Float64:
		rational := new(big.Rat)
		if rational.SetFloat64(reflected.Float()) == nil {
			return nil, false
		}
		return rational, true
	default:
		return nil, false
	}
}

func canonicalJSON(value any) ([]byte, error) {
	normalized, err := normalizePythonJSONValue(value)
	if err != nil {
		return nil, err
	}

	var buffer bytes.Buffer
	encoder := json.NewEncoder(&buffer)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(normalized); err != nil {
		return nil, err
	}
	encoded := bytes.TrimSuffix(buffer.Bytes(), []byte{'\n'})
	return unescapeJSONLineSeparators(encoded), nil
}

func normalizePythonJSONValue(value any) (any, error) {
	switch typed := value.(type) {
	case json.Number:
		return typed, nil
	case json.RawMessage:
		return typed, nil
	case []byte:
		return typed, nil
	case float64:
		return pythonFloatJSONNumber(typed)
	case float32:
		return pythonFloatJSONNumber(float64(typed))
	}

	reflected := reflect.ValueOf(value)
	if !reflected.IsValid() {
		return nil, nil
	}

	switch reflected.Kind() {
	case reflect.Interface, reflect.Pointer:
		if reflected.IsNil() {
			return nil, nil
		}
		return normalizePythonJSONValue(reflected.Elem().Interface())
	case reflect.Map:
		if reflected.IsNil() || reflected.Type().Key().Kind() != reflect.String {
			return value, nil
		}
		normalized := make(map[string]any, reflected.Len())
		for _, key := range reflected.MapKeys() {
			item, err := normalizePythonJSONValue(reflected.MapIndex(key).Interface())
			if err != nil {
				return nil, err
			}
			normalized[key.String()] = item
		}
		return normalized, nil
	case reflect.Slice:
		if reflected.IsNil() || reflected.Type().Elem().Kind() == reflect.Uint8 {
			return value, nil
		}
		fallthrough
	case reflect.Array:
		normalized := make([]any, reflected.Len())
		for index := 0; index < reflected.Len(); index++ {
			item, err := normalizePythonJSONValue(reflected.Index(index).Interface())
			if err != nil {
				return nil, err
			}
			normalized[index] = item
		}
		return normalized, nil
	default:
		return value, nil
	}
}

// pythonFloatJSONNumber preserves Python json.dumps float notation while
// retaining Go's shortest round-trippable decimal digits.
func pythonFloatJSONNumber(value float64) (json.Number, error) {
	if math.IsNaN(value) || math.IsInf(value, 0) {
		return "", errors.New("non-finite floats are not supported in canonical JSON")
	}

	scientific := strconv.FormatFloat(value, 'e', -1, 64)
	parts := strings.SplitN(scientific, "e", 2)
	if len(parts) != 2 {
		return "", errors.New("invalid canonical float representation")
	}
	exponent, err := strconv.Atoi(parts[1])
	if err != nil {
		return "", err
	}
	if exponent < -4 || exponent >= 16 {
		return json.Number(scientific), nil
	}

	mantissa := parts[0]
	sign := ""
	if strings.HasPrefix(mantissa, "-") {
		sign = "-"
		mantissa = strings.TrimPrefix(mantissa, "-")
	}
	digits := strings.ReplaceAll(mantissa, ".", "")
	decimalPosition := exponent + 1

	var fixed string
	switch {
	case decimalPosition <= 0:
		fixed = "0." + strings.Repeat("0", -decimalPosition) + digits
	case decimalPosition >= len(digits):
		fixed = digits + strings.Repeat("0", decimalPosition-len(digits)) + ".0"
	default:
		fixed = digits[:decimalPosition] + "." + digits[decimalPosition:]
	}
	return json.Number(sign + fixed), nil
}

// Python json.dumps(ensure_ascii=false) emits U+2028/U+2029 literally.
// Go encoding/json always escapes them, so unescape only real JSON unicode
// escapes while preserving escaped backslash sequences.
func unescapeJSONLineSeparators(encoded []byte) []byte {
	result := make([]byte, 0, len(encoded))
	for index := 0; index < len(encoded); {
		if encoded[index] == '\\' && index+1 < len(encoded) {
			if encoded[index+1] == '\\' {
				result = append(result, encoded[index], encoded[index+1])
				index += 2
				continue
			}
			if index+5 < len(encoded) &&
				encoded[index+1] == 'u' &&
				encoded[index+2] == '2' &&
				encoded[index+3] == '0' &&
				encoded[index+4] == '2' {
				switch encoded[index+5] {
				case '8':
					result = append(result, []byte("\u2028")...)
					index += 6
					continue
				case '9':
					result = append(result, []byte("\u2029")...)
					index += 6
					continue
				}
			}
			result = append(result, encoded[index], encoded[index+1])
			index += 2
			continue
		}
		result = append(result, encoded[index])
		index++
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
	value = value.UTC().Truncate(time.Microsecond)
	if value.Nanosecond() == 0 {
		return value.Format("2006-01-02T15:04:05+00:00")
	}
	return value.Format("2006-01-02T15:04:05.000000+00:00")
}
}
