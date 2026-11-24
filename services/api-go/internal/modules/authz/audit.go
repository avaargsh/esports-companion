package authz

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/idgen"
)

type AuditRepository struct {
	db *pgxpool.Pool
}

func NewAuditRepository(db *pgxpool.Pool) AuditRepository {
	return AuditRepository{db: db}
}

func (r AuditRepository) RecordDecision(
	ctx context.Context,
	decision AuthorizationDecision,
	authority *AuthorityEnvelope,
) error {
	payload := decision.Payload()
	if authority != nil {
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
	id, err := idgen.UUIDv4()
	if err != nil {
		return err
	}
	encoded, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	if _, err := r.db.Exec(ctx, `
		INSERT INTO outbox_events (
			id, aggregate_type, aggregate_id, event_type, payload_json, status
		)
		VALUES ($1::uuid, 'AUDIT', $2, $3, $4::json, 'PENDING')
	`, id, aggregateID, eventType, string(encoded)); err != nil {
		return fmt.Errorf("insert authorization audit: %w", err)
	}
	return nil
}
