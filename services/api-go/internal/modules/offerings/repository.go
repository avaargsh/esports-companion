package offerings

import (
	"context"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/idgen"
)

var (
	ErrPlayerProfileNotFound = errors.New("PLAYER_PROFILE_NOT_FOUND")
	ErrSKUNotFound           = errors.New("SKU_NOT_FOUND")
	ErrOfferingAlreadyExists = errors.New("OFFERING_ALREADY_EXISTS")
)

type Repository struct {
	db *pgxpool.Pool
}

func NewRepository(db *pgxpool.Pool) Repository {
	return Repository{db: db}
}

func (r Repository) ListForUser(ctx context.Context, userID string) ([]Offering, error) {
	playerID, err := playerIDForUser(ctx, r.db, userID)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrPlayerProfileNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("load player profile: %w", err)
	}

	rows, err := r.db.Query(ctx, `
		SELECT id::text, player_id::text, sku_id::text,
		       price_override, description, status
		FROM provider_offerings
		WHERE player_id = $1::uuid
		ORDER BY created_at
	`, playerID)
	if err != nil {
		return nil, fmt.Errorf("list provider offerings: %w", err)
	}
	defer rows.Close()

	result := make([]Offering, 0)
	for rows.Next() {
		item, err := scanOffering(rows)
		if err != nil {
			return nil, err
		}
		result = append(result, item)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate provider offerings: %w", err)
	}
	return result, nil
}

func (r Repository) UpsertForUser(
	ctx context.Context,
	userID string,
	skuID string,
	input Upsert,
) (Offering, error) {
	tx, err := r.db.Begin(ctx)
	if err != nil {
		return Offering{}, err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	playerID, err := playerIDForUser(ctx, tx, userID)
	if errors.Is(err, pgx.ErrNoRows) {
		return Offering{}, ErrPlayerProfileNotFound
	}
	if err != nil {
		return Offering{}, fmt.Errorf("load player profile: %w", err)
	}

	var skuExists bool
	if err := tx.QueryRow(ctx, `
		SELECT EXISTS(SELECT 1 FROM service_skus WHERE id = $1::uuid)
	`, skuID).Scan(&skuExists); err != nil {
		return Offering{}, fmt.Errorf("check sku: %w", err)
	}
	if !skuExists {
		return Offering{}, ErrSKUNotFound
	}

	item, err := scanOffering(tx.QueryRow(ctx, `
		SELECT id::text, player_id::text, sku_id::text,
		       price_override, description, status
		FROM provider_offerings
		WHERE player_id = $1::uuid AND sku_id = $2::uuid
	`, playerID, skuID))
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return Offering{}, fmt.Errorf("load provider offering: %w", err)
	}

	if errors.Is(err, pgx.ErrNoRows) {
		id, err := idgen.UUIDv4()
		if err != nil {
			return Offering{}, err
		}
		item, err = scanOffering(tx.QueryRow(ctx, `
			INSERT INTO provider_offerings (
				id, player_id, sku_id, price_override, description, status
			)
			VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6)
			RETURNING id::text, player_id::text, sku_id::text,
			          price_override, description, status
		`, id, playerID, skuID, input.PriceOverride, input.Description, input.Status))
		if err != nil {
			var pgErr *pgconn.PgError
			if errors.As(err, &pgErr) && pgErr.Code == "23505" {
				return Offering{}, ErrOfferingAlreadyExists
			}
			return Offering{}, fmt.Errorf("insert provider offering: %w", err)
		}
	} else {
		item, err = scanOffering(tx.QueryRow(ctx, `
			UPDATE provider_offerings
			SET price_override = $2,
			    description = $3,
			    status = $4,
			    updated_at = now()
			WHERE id = $1::uuid
			RETURNING id::text, player_id::text, sku_id::text,
			          price_override, description, status
		`, item.ID, input.PriceOverride, input.Description, input.Status))
		if err != nil {
			return Offering{}, fmt.Errorf("update provider offering: %w", err)
		}
	}

	if err := tx.Commit(ctx); err != nil {
		return Offering{}, err
	}
	return item, nil
}

type queryRower interface {
	QueryRow(context.Context, string, ...any) pgx.Row
}

func playerIDForUser(ctx context.Context, q queryRower, userID string) (string, error) {
	var playerID string
	err := q.QueryRow(ctx, `
		SELECT id::text
		FROM player_profiles
		WHERE user_id = $1::uuid
	`, userID).Scan(&playerID)
	return playerID, err
}

type scanner interface {
	Scan(...any) error
}

func scanOffering(row scanner) (Offering, error) {
	var item Offering
	var price pgtype.Int4
	if err := row.Scan(
		&item.ID,
		&item.PlayerID,
		&item.SKUID,
		&price,
		&item.Description,
		&item.Status,
	); err != nil {
		return Offering{}, err
	}
	if price.Valid {
		value := int(price.Int32)
		item.PriceOverride = &value
	}
	return item, nil
}
