package authz

import (
	"context"
	"errors"
	"fmt"
	"reflect"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"

	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/idgen"
)

type auditTransaction interface {
	Exec(context.Context, string, ...any) (pgconn.CommandTag, error)
	Commit(context.Context) error
	Rollback(context.Context) error
}

var _ auditTransaction = (pgx.Tx)(nil)

type AuditRepository struct {
	tx auditTransaction
}

// NewAuditRepository binds audit writes to the caller's transaction. A pgx.Tx
// satisfies this narrow interface; a pgxpool.Pool does not because it cannot
// commit or roll back a caller-owned transaction.
func NewAuditRepository(tx auditTransaction) (AuditRepository, error) {
	value := reflect.ValueOf(tx)
	if tx == nil || (value.Kind() == reflect.Ptr && value.IsNil()) {
		return AuditRepository{}, errors.New("authorization audit requires caller transaction")
	}
	return AuditRepository{tx: tx}, nil
}

func (r AuditRepository) RecordDecision(
	ctx context.Context,
	decision AuthorizationDecision,
	authority *AuthorityEnvelope,
) error {
	payload := decision.Payload()
	if authority != nil {
		if !reflect.DeepEqual(payload, authority.Authorization.Payload()) {
			return errors.New("authorization audit decision does not match authority envelope")
		}
		authorityPayload, err := authority.Payload()
		if err != nil {
			return err
		}
		payload["authorityEnvelope"] = authorityPayload
	}
	return r.insert(
		ctx,
		fmt.Sprintf("%s:%s", decision.ResourceType, decision.ResourceID),
		"AUTHORIZATION_DECISION",
		payload,
	)
}

func (r AuditRepository) RecordAdmission(
	ctx context.Context,
	authority AuthorityEnvelope,
	admission AuthorityAdmissionDecision,
) error {
	digest, err := authority.Digest()
	if err != nil {
		return err
	}
	if admission.AuthorityDigest != digest {
		return errors.New("authority admission digest does not match envelope")
	}
	authorityPayload, err := authority.Payload()
	if err != nil {
		return err
	}
	payload := map[string]any{
		"authorization":     authority.Authorization.Payload(),
		"authorityEnvelope": authorityPayload,
		"admission":         admission.Payload(),
	}
	return r.insert(
		ctx,
		fmt.Sprintf(
			"%s:%s",
			authority.Authorization.ResourceType,
			authority.Authorization.ResourceID,
		),
		"AUTHORITY_ADMISSION",
		payload,
	)
}

func (r AuditRepository) insert(
	ctx context.Context,
	aggregateID string,
	eventType string,
	payload map[string]any,
) error {
	if r.tx == nil {
		return errors.New("authorization audit requires caller transaction")
	}
	id, err := idgen.UUIDv4()
	if err != nil {
		return err
	}
	// Preserve the number representation used by the envelope digest.
	encoded, err := canonicalJSON(payload)
	if err != nil {
		return err
	}
	if _, err := r.tx.Exec(ctx, `
		INSERT INTO outbox_events (
			id, aggregate_type, aggregate_id, event_type, payload_json, status
		)
		VALUES ($1::uuid, 'AUDIT', $2, $3, $4::json, 'PENDING')
	`, id, aggregateID, eventType, string(encoded)); err != nil {
		return fmt.Errorf("insert authorization audit: %w", err)
	}
	return nil
}
