package realtime

import (
	"context"
	"fmt"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/auth"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/httpx"
)

type Repository struct {
	db *pgxpool.Pool
}

func NewRepository(db *pgxpool.Pool) Repository {
	return Repository{db: db}
}

func (r Repository) AuthorizeChannels(
	ctx context.Context,
	principal auth.Principal,
	channels []string,
) ([]string, []string, error) {
	accepted := make([]string, 0)
	rejected := make([]string, 0)

	for _, channel := range channels[:min(20, len(channels))] {
		switch {
		case strings.HasPrefix(channel, "user:"):
			userID := strings.TrimPrefix(channel, "user:")
			if !httpx.IsUUID(userID) {
				rejected = append(rejected, channel)
				continue
			}
			if userID == principal.User.ID || hasRole(principal.Roles, "PLATFORM") {
				accepted = append(accepted, channel)
			} else {
				rejected = append(rejected, channel)
			}

		case strings.HasPrefix(channel, "order:"):
			orderID := strings.TrimPrefix(channel, "order:")
			if !httpx.IsUUID(orderID) {
				rejected = append(rejected, channel)
				continue
			}
			var ownerID string
			err := r.db.QueryRow(ctx, `
				SELECT user_id::text
				FROM orders
				WHERE id = $1::uuid
			`, orderID).Scan(&ownerID)
			if err == pgx.ErrNoRows {
				rejected = append(rejected, channel)
				continue
			}
			if err != nil {
				return nil, nil, fmt.Errorf("load realtime order: %w", err)
			}
			if ownerID == principal.User.ID || hasRole(principal.Roles, "PLATFORM") {
				accepted = append(accepted, channel)
				continue
			}

			var participant bool
			if err := r.db.QueryRow(ctx, `
				SELECT EXISTS(
					SELECT 1
					FROM order_assignments a
					JOIN player_profiles p ON p.id = a.player_id
					WHERE a.order_id = $1::uuid
					  AND a.status = 'ACTIVE'
					  AND p.user_id = $2::uuid
				)
			`, orderID, principal.User.ID).Scan(&participant); err != nil {
				return nil, nil, fmt.Errorf("load realtime order participant: %w", err)
			}
			if participant {
				accepted = append(accepted, channel)
			} else {
				rejected = append(rejected, channel)
			}

		default:
			rejected = append(rejected, channel)
		}
	}
	return accepted, rejected, nil
}

func (r Repository) OrderAllowedUsers(
	ctx context.Context,
	orderID string,
) (map[string]struct{}, error) {
	allowed := make(map[string]struct{}, 2)
	var ownerID string
	err := r.db.QueryRow(ctx, `
		SELECT user_id::text
		FROM orders
		WHERE id::text = $1
	`, orderID).Scan(&ownerID)
	if err == pgx.ErrNoRows {
		return allowed, nil
	}
	if err != nil {
		return nil, fmt.Errorf("load realtime order owner: %w", err)
	}
	allowed[ownerID] = struct{}{}

	var playerUserID string
	err = r.db.QueryRow(ctx, `
		SELECT p.user_id::text
		FROM order_assignments a
		JOIN player_profiles p ON p.id = a.player_id
		WHERE a.order_id = $1::uuid
		  AND a.status = 'ACTIVE'
		ORDER BY a.created_at DESC
		LIMIT 1
	`, orderID).Scan(&playerUserID)
	if err != nil && err != pgx.ErrNoRows {
		return nil, fmt.Errorf("load realtime active player: %w", err)
	}
	if err == nil {
		allowed[playerUserID] = struct{}{}
	}
	return allowed, nil
}

func hasRole(roles []string, expected string) bool {
	for _, role := range roles {
		if role == expected {
			return true
		}
	}
	return false
}
