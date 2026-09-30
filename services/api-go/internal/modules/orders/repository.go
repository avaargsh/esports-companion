package orders

import (
	"context"
	"errors"
	"fmt"

	"github.com/go-chi/chi/v5/middleware"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/auth"
	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/authz"
)

var ErrOrderNotFound = errors.New("ORDER_NOT_FOUND")

type scanner interface {
	Scan(...any) error
}

type Repository struct {
	db *pgxpool.Pool
}

func NewRepository(db *pgxpool.Pool) Repository {
	return Repository{db: db}
}

func (r Repository) ListForUser(ctx context.Context, userID string, limit int) ([]Order, error) {
	rows, err := r.db.Query(ctx, `
		SELECT
			id::text,
			order_no,
			user_id::text,
			game_id::text,
			sku_id::text,
			designated_player_id::text,
			status,
			quantity,
			unit_price,
			total_amount,
			player_amount,
			platform_fee,
			version
		FROM orders
		WHERE user_id = $1::uuid
		ORDER BY created_at DESC
		LIMIT $2
	`, userID, limit)
	if err != nil {
		return nil, fmt.Errorf("list orders: %w", err)
	}
	defer rows.Close()

	items := make([]Order, 0)
	for rows.Next() {
		item, err := scanOrder(rows)
		if err != nil {
			return nil, fmt.Errorf("scan order: %w", err)
		}
		items = append(items, item)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate orders: %w", err)
	}
	return items, nil
}

func (r Repository) Get(ctx context.Context, orderID string) (Order, error) {
	item, err := scanOrder(r.db.QueryRow(ctx, `
		SELECT
			id::text,
			order_no,
			user_id::text,
			game_id::text,
			sku_id::text,
			designated_player_id::text,
			status,
			quantity,
			unit_price,
			total_amount,
			player_amount,
			platform_fee,
			version
		FROM orders
		WHERE id = $1::uuid
	`, orderID))
	if errors.Is(err, pgx.ErrNoRows) {
		return Order{}, ErrOrderNotFound
	}
	if err != nil {
		return Order{}, fmt.Errorf("get order: %w", err)
	}
	return item, nil
}

func scanOrder(row scanner) (Order, error) {
	var item Order
	var designated pgtype.Text
	if err := row.Scan(
		&item.ID,
		&item.OrderNo,
		&item.UserID,
		&item.GameID,
		&item.SKUID,
		&designated,
		&item.Status,
		&item.Quantity,
		&item.UnitPrice,
		&item.TotalAmount,
		&item.PlayerAmount,
		&item.PlatformFee,
		&item.Version,
	); err != nil {
		return Order{}, err
	}
	if designated.Valid {
		value := designated.String
		item.DesignatedPlayerID = &value
	}
	return item, nil
}

func (r Repository) Detail(ctx context.Context, order Order) (Detail, error) {
	player, err := r.activeServicePlayer(ctx, order.ID)
	if errors.Is(err, pgx.ErrNoRows) && order.DesignatedPlayerID != nil {
		player, err = r.designatedServicePlayer(ctx, *order.DesignatedPlayerID)
	}
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return Detail{}, err
	}
	var servicePlayer *ServicePlayer
	if err == nil {
		servicePlayer = &player
	}
	return Detail{
		Order:            order,
		ServicePlayer:    servicePlayer,
		AvailableActions: availableActions(order.Status),
	}, nil
}

func (r Repository) activeServicePlayer(ctx context.Context, orderID string) (ServicePlayer, error) {
	var item ServicePlayer
	var avatar pgtype.Text
	var assignedBy pgtype.Text
	if err := r.db.QueryRow(ctx, `
		SELECT
			p.id::text,
			p.display_name,
			u.avatar_url,
			p.rating::float8,
			p.service_status,
			a.assigned_by
		FROM order_assignments a
		JOIN player_profiles p ON p.id = a.player_id
		LEFT JOIN users u ON u.id = p.user_id
		WHERE a.order_id = $1::uuid
		  AND a.status = 'ACTIVE'
		ORDER BY a.created_at DESC
		LIMIT 1
	`, orderID).Scan(
		&item.ID,
		&item.DisplayName,
		&avatar,
		&item.Rating,
		&item.ServiceStatus,
		&assignedBy,
	); err != nil {
		return ServicePlayer{}, err
	}
	if avatar.Valid {
		value := avatar.String
		item.AvatarURL = &value
	}
	if assignedBy.Valid {
		value := assignedBy.String
		item.AssignedBy = &value
	}
	item.Binding = "ASSIGNED"
	return item, nil
}

func (r Repository) designatedServicePlayer(ctx context.Context, playerID string) (ServicePlayer, error) {
	var item ServicePlayer
	var avatar pgtype.Text
	if err := r.db.QueryRow(ctx, `
		SELECT
			p.id::text,
			p.display_name,
			u.avatar_url,
			p.rating::float8,
			p.service_status
		FROM player_profiles p
		LEFT JOIN users u ON u.id = p.user_id
		WHERE p.id = $1::uuid
	`, playerID).Scan(
		&item.ID,
		&item.DisplayName,
		&avatar,
		&item.Rating,
		&item.ServiceStatus,
	); err != nil {
		return ServicePlayer{}, err
	}
	if avatar.Valid {
		value := avatar.String
		item.AvatarURL = &value
	}
	item.Binding = "DESIGNATED"
	return item, nil
}

func (r Repository) Events(ctx context.Context, orderID string) ([]Event, error) {
	rows, err := r.db.Query(ctx, `
		SELECT
			id::text,
			event_type,
			from_status,
			to_status,
			actor_type,
			created_at
		FROM order_events
		WHERE order_id = $1::uuid
		ORDER BY created_at, id
	`, orderID)
	if err != nil {
		return nil, fmt.Errorf("list order events: %w", err)
	}
	defer rows.Close()

	items := make([]Event, 0)
	for rows.Next() {
		var item Event
		var fromStatus pgtype.Text
		var toStatus pgtype.Text
		if err := rows.Scan(
			&item.ID,
			&item.EventType,
			&fromStatus,
			&toStatus,
			&item.ActorType,
			&item.CreatedAt,
		); err != nil {
			return nil, fmt.Errorf("scan order event: %w", err)
		}
		if fromStatus.Valid {
			value := fromStatus.String
			item.FromStatus = &value
		}
		if toStatus.Valid {
			value := toStatus.String
			item.ToStatus = &value
		}
		items = append(items, item)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate order events: %w", err)
	}
	return items, nil
}

func (r Repository) AuthorizeViewer(
	ctx context.Context,
	order Order,
	principal auth.Principal,
) (authz.AuthorizationDecision, error) {
	requestID := middleware.GetReqID(ctx)
	common := authz.AuthorizationDecision{
		ActorUserID:         principal.User.ID,
		ActorRoles:          append([]string(nil), principal.Roles...),
		Action:              "ORDER_READ",
		ResourceType:        "ORDER",
		ResourceID:          order.ID,
		PolicyVersion:       authz.PolicyVersion,
		SessionID:           principal.SessionID,
		RequestID:           requestID,
		BusinessEvidenceRef: fmt.Sprintf("ORDER:%s", order.ID),
	}

	if principal.User.ID == order.UserID {
		return authz.RequireOwner(authz.OwnerPolicyInput{
			ActorUserID:         principal.User.ID,
			ActorRoles:          principal.Roles,
			OwnerUserID:         order.UserID,
			Action:              common.Action,
			ResourceType:        common.ResourceType,
			ResourceID:          common.ResourceID,
			SessionID:           common.SessionID,
			RequestID:           common.RequestID,
			BusinessEvidenceRef: common.BusinessEvidenceRef,
		})
	}
	if hasRole(principal.Roles, "PLATFORM") {
		return authz.RequirePlatform(authz.PlatformPolicyInput{
			ActorUserID:         principal.User.ID,
			ActorRoles:          principal.Roles,
			Action:              common.Action,
			ResourceType:        common.ResourceType,
			ResourceID:          common.ResourceID,
			SessionID:           common.SessionID,
			RequestID:           common.RequestID,
			BusinessEvidenceRef: common.BusinessEvidenceRef,
		})
	}
	if hasRole(principal.Roles, "PLAYER") {
		var participant bool
		if err := r.db.QueryRow(ctx, `
			SELECT EXISTS(
				SELECT 1
				FROM player_profiles p
				JOIN order_assignments a ON a.player_id = p.id
				WHERE p.user_id = $1::uuid
				  AND a.order_id = $2::uuid
				  AND a.status = 'ACTIVE'
			)
		`, principal.User.ID, order.ID).Scan(&participant); err != nil {
			return authz.AuthorizationDecision{}, fmt.Errorf("resolve order participant: %w", err)
		}
		if participant {
			common.Scope = "PARTICIPANT"
			common.Decision = "ALLOW"
			common.ReasonCode = "ACTIVE_ASSIGNMENT"
			return common, nil
		}
	}

	common.Scope = "ORDER"
	common.Decision = "DENY"
	common.ReasonCode = "ORDER_ACCESS_DENIED"
	return authz.AuthorizationDecision{}, &authz.ResourceAuthorizationDenied{
		Decision: common,
	}
}

func hasRole(roles []string, role string) bool {
	for _, candidate := range roles {
		if candidate == role {
			return true
		}
	}
	return false
}
