package catalog

import (
	"context"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"
)

var ErrGameNotFound = errors.New("GAME_NOT_FOUND")

type Repository struct {
	db *pgxpool.Pool
}

func NewRepository(db *pgxpool.Pool) Repository {
	return Repository{db: db}
}

func (r Repository) ListGames(ctx context.Context) ([]Game, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id::text, code, name, icon_url
		FROM games
		WHERE status = 'ACTIVE'
		ORDER BY sort_order
	`)
	if err != nil {
		return nil, fmt.Errorf("list games: %w", err)
	}
	defer rows.Close()

	result := make([]Game, 0)
	for rows.Next() {
		var item Game
		var icon pgtype.Text
		if err := rows.Scan(&item.ID, &item.Code, &item.Name, &icon); err != nil {
			return nil, fmt.Errorf("scan game: %w", err)
		}
		if icon.Valid {
			value := icon.String
			item.IconURL = &value
		}
		result = append(result, item)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate games: %w", err)
	}
	return result, nil
}

func (r Repository) ListSKUs(ctx context.Context, gameID string) ([]SKU, error) {
	var exists bool
	if err := r.db.QueryRow(ctx, `
		SELECT EXISTS(
			SELECT 1 FROM games WHERE id = $1::uuid AND status = 'ACTIVE'
		)
	`, gameID).Scan(&exists); err != nil {
		return nil, fmt.Errorf("check game: %w", err)
	}
	if !exists {
		return nil, ErrGameNotFound
	}

	rows, err := r.db.Query(ctx, `
		SELECT id::text, game_id::text, name, service_type, duration_minutes, price
		FROM service_skus
		WHERE game_id = $1::uuid AND status = 'ACTIVE'
	`, gameID)
	if err != nil {
		return nil, fmt.Errorf("list skus: %w", err)
	}
	defer rows.Close()

	result := make([]SKU, 0)
	for rows.Next() {
		var item SKU
		if err := rows.Scan(
			&item.ID,
			&item.GameID,
			&item.Name,
			&item.ServiceType,
			&item.DurationMinutes,
			&item.Price,
		); err != nil {
			return nil, fmt.Errorf("scan sku: %w", err)
		}
		result = append(result, item)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate skus: %w", err)
	}
	return result, nil
}
