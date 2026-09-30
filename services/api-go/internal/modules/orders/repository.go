package orders

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/auth"
	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/authz"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/httpx"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/idgen"
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

func (r Repository) Create(
	ctx context.Context,
	userID string,
	input CreateInput,
) (Order, error) {
	tx, err := r.db.Begin(ctx)
	if err != nil {
		return Order{}, fmt.Errorf("begin order create: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	var (
		skuID              string
		gameID             string
		unitPrice          int
		platformFeeRate    string
		designatedPlayerID *string
	)

	if input.OfferingID != nil {
		var (
			offeringStatus string
			playerID       string
			offeringSKUID  string
			priceOverride  pgtype.Int4
		)
		err := tx.QueryRow(ctx, `
			SELECT status, player_id::text, sku_id::text, price_override
			FROM provider_offerings
			WHERE id = $1::uuid
		`, *input.OfferingID).Scan(
			&offeringStatus,
			&playerID,
			&offeringSKUID,
			&priceOverride,
		)
		if errors.Is(err, pgx.ErrNoRows) || (err == nil && offeringStatus != "ACTIVE") {
			return Order{}, ErrOfferingNotAvailable
		}
		if err != nil {
			return Order{}, fmt.Errorf("load offering: %w", err)
		}

		var (
			playerUserID       string
			verificationStatus string
			serviceStatus      string
		)
		err = tx.QueryRow(ctx, `
			SELECT user_id::text, verification_status, service_status
			FROM player_profiles
			WHERE id = $1::uuid
		`, playerID).Scan(
			&playerUserID,
			&verificationStatus,
			&serviceStatus,
		)
		if errors.Is(err, pgx.ErrNoRows) ||
			(err == nil && (verificationStatus != "APPROVED" || serviceStatus != "AVAILABLE")) {
			return Order{}, ErrPlayerNotAvailable
		}
		if err != nil {
			return Order{}, fmt.Errorf("load offering player: %w", err)
		}
		if playerUserID == userID {
			return Order{}, ErrCannotOrderOwnOffering
		}

		skuID = offeringSKUID
		designatedPlayerID = &playerID

		skuPrice, skuGameID, rate, err := loadActiveSKU(ctx, tx, skuID)
		if err != nil {
			return Order{}, err
		}
		gameID = skuGameID
		platformFeeRate = rate
		if priceOverride.Valid {
			unitPrice = int(priceOverride.Int32)
		} else {
			unitPrice = skuPrice
		}
	} else {
		skuPrice, skuGameID, rate, err := loadActiveSKU(ctx, tx, *input.SKUID)
		if err != nil {
			return Order{}, err
		}
		skuID = *input.SKUID
		gameID = skuGameID
		unitPrice = skuPrice
		platformFeeRate = rate
	}

	var gameStatus string
	err = tx.QueryRow(ctx, `
		SELECT status
		FROM games
		WHERE id = $1::uuid
	`, gameID).Scan(&gameStatus)
	if errors.Is(err, pgx.ErrNoRows) || (err == nil && gameStatus != "ACTIVE") {
		return Order{}, ErrGameNotAvailable
	}
	if err != nil {
		return Order{}, fmt.Errorf("load order game: %w", err)
	}

	rate, err := strconv.ParseFloat(platformFeeRate, 64)
	if err != nil {
		return Order{}, fmt.Errorf("parse platform fee rate: %w", err)
	}
	total := unitPrice * input.Quantity
	platformFee := int(float64(total) * rate)
	playerAmount := total - platformFee

	orderID, err := idgen.UUIDv4()
	if err != nil {
		return Order{}, err
	}
	orderNoUUID, err := idgen.UUIDv4()
	if err != nil {
		return Order{}, err
	}
	orderNo := "ORD_" + strings.ToUpper(strings.ReplaceAll(orderNoUUID, "-", ""))[:20]

	var designated any
	if designatedPlayerID != nil {
		designated = *designatedPlayerID
	}
	if _, err := tx.Exec(ctx, `
		INSERT INTO orders (
			id, order_no, user_id, game_id, sku_id, designated_player_id,
			status, quantity, unit_price, total_amount, player_amount,
			platform_fee, remark, version
		)
		VALUES (
			$1::uuid, $2, $3::uuid, $4::uuid, $5::uuid, $6::uuid,
			'WAITING_PAYMENT', $7, $8, $9, $10, $11, $12, 0
		)
	`,
		orderID,
		orderNo,
		userID,
		gameID,
		skuID,
		designated,
		input.Quantity,
		unitPrice,
		total,
		playerAmount,
		platformFee,
		input.Remark,
	); err != nil {
		return Order{}, fmt.Errorf("insert order: %w", err)
	}

	eventPayload := map[string]any{
		"designatedPlayerId": nil,
	}
	if designatedPlayerID != nil {
		eventPayload["designatedPlayerId"] = *designatedPlayerID
	}
	if err := appendOrderEvidence(
		ctx,
		tx,
		orderID,
		"ORDER_CREATED",
		nil,
		"WAITING_PAYMENT",
		"USER",
		userID,
		eventPayload,
	); err != nil {
		return Order{}, err
	}

	if err := tx.Commit(ctx); err != nil {
		return Order{}, fmt.Errorf("commit order create: %w", err)
	}

	return Order{
		ID:                 orderID,
		OrderNo:            orderNo,
		UserID:             userID,
		GameID:             gameID,
		SKUID:              skuID,
		DesignatedPlayerID: designatedPlayerID,
		Status:             "WAITING_PAYMENT",
		Quantity:           input.Quantity,
		UnitPrice:          unitPrice,
		TotalAmount:        total,
		PlayerAmount:       playerAmount,
		PlatformFee:        platformFee,
		Version:            0,
	}, nil
}

func loadActiveSKU(
	ctx context.Context,
	tx pgx.Tx,
	skuID string,
) (price int, gameID string, platformFeeRate string, err error) {
	var status string
	err = tx.QueryRow(ctx, `
		SELECT price, game_id::text, platform_fee_rate::text, status
		FROM service_skus
		WHERE id = $1::uuid
	`, skuID).Scan(&price, &gameID, &platformFeeRate, &status)
	if errors.Is(err, pgx.ErrNoRows) || (err == nil && status != "ACTIVE") {
		return 0, "", "", ErrSKUNotAvailable
	}
	if err != nil {
		return 0, "", "", fmt.Errorf("load sku: %w", err)
	}
	return price, gameID, platformFeeRate, nil
}

func (r Repository) Claim(
	ctx context.Context,
	userID string,
	orderID string,
	expectedVersion int,
) (Order, error) {
	tx, err := r.db.Begin(ctx)
	if err != nil {
		return Order{}, fmt.Errorf("begin order claim: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	var (
		playerID           string
		verificationStatus string
		serviceStatus      string
	)
	err = tx.QueryRow(ctx, `
		SELECT id::text, verification_status, service_status
		FROM player_profiles
		WHERE user_id = $1::uuid
	`, userID).Scan(&playerID, &verificationStatus, &serviceStatus)
	if errors.Is(err, pgx.ErrNoRows) ||
		(err == nil && (verificationStatus != "APPROVED" || serviceStatus != "AVAILABLE")) {
		return Order{}, ErrPlayerNotEligible
	}
	if err != nil {
		return Order{}, fmt.Errorf("load claim player: %w", err)
	}

	order, err := scanOrder(tx.QueryRow(ctx, `
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
		return Order{}, fmt.Errorf("load claim order: %w", err)
	}
	if order.UserID == userID {
		return Order{}, ErrCannotClaimOwnOrder
	}
	if order.Status != "MATCHING" {
		return Order{}, ErrOrderAlreadyAccepted
	}

	var offeringExists bool
	if err := tx.QueryRow(ctx, `
		SELECT EXISTS(
			SELECT 1
			FROM provider_offerings
			WHERE player_id = $1::uuid
			  AND sku_id = $2::uuid
			  AND status = 'ACTIVE'
		)
	`, playerID, order.SKUID).Scan(&offeringExists); err != nil {
		return Order{}, fmt.Errorf("check claim offering: %w", err)
	}
	if !offeringExists {
		return Order{}, ErrPlayerNotOfferingSKU
	}

	claimed, err := scanOrder(tx.QueryRow(ctx, `
		UPDATE orders
		SET status = 'ACCEPTED',
		    version = version + 1,
		    accepted_at = now(),
		    updated_at = now()
		WHERE id = $1::uuid
		  AND status = 'MATCHING'
		  AND version = $2
		RETURNING
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
	`, orderID, expectedVersion))
	if errors.Is(err, pgx.ErrNoRows) {
		return Order{}, ErrOrderAlreadyAccepted
	}
	if err != nil {
		return Order{}, fmt.Errorf("claim order compare-and-swap: %w", err)
	}

	assignmentID, err := idgen.UUIDv4()
	if err != nil {
		return Order{}, err
	}
	if _, err := tx.Exec(ctx, `
		INSERT INTO order_assignments (
			id, order_id, player_id, status, assigned_by, accepted_at
		)
		VALUES (
			$1::uuid, $2::uuid, $3::uuid, 'ACTIVE', 'PLAYER', now()
		)
	`, assignmentID, orderID, playerID); err != nil {
		return Order{}, fmt.Errorf("insert active assignment: %w", err)
	}

	fromStatus := "MATCHING"
	if err := appendOrderEvidence(
		ctx,
		tx,
		orderID,
		"PLAYER_CLAIMED",
		&fromStatus,
		"ACCEPTED",
		"PLAYER",
		playerID,
		map[string]any{},
	); err != nil {
		return Order{}, err
	}

	if err := tx.Commit(ctx); err != nil {
		return Order{}, fmt.Errorf("commit order claim: %w", err)
	}
	return claimed, nil
}

func (r Repository) TransitionAssignedPlayer(
	ctx context.Context,
	userID string,
	orderID string,
	target Status,
	eventType string,
) (Order, error) {
	tx, err := r.db.Begin(ctx)
	if err != nil {
		return Order{}, fmt.Errorf("begin order lifecycle transition: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	order, err := scanOrder(tx.QueryRow(ctx, `
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
		FOR UPDATE
	`, orderID))
	if errors.Is(err, pgx.ErrNoRows) {
		return Order{}, ErrOrderNotFound
	}
	if err != nil {
		return Order{}, fmt.Errorf("lock lifecycle order: %w", err)
	}

	var playerID string
	if err := tx.QueryRow(ctx, `
		SELECT id::text
		FROM player_profiles
		WHERE user_id = $1::uuid
	`, userID).Scan(&playerID); errors.Is(err, pgx.ErrNoRows) {
		return Order{}, ErrPlayerNotEligible
	} else if err != nil {
		return Order{}, fmt.Errorf("load lifecycle player: %w", err)
	}

	var assignedPlayerID string
	if err := tx.QueryRow(ctx, `
		SELECT player_id::text
		FROM order_assignments
		WHERE order_id = $1::uuid
		  AND status = 'ACTIVE'
		ORDER BY created_at DESC
		LIMIT 1
	`, orderID).Scan(&assignedPlayerID); errors.Is(err, pgx.ErrNoRows) {
		return Order{}, ErrAssignmentNotFound
	} else if err != nil {
		return Order{}, fmt.Errorf("load active assignment: %w", err)
	}
	if assignedPlayerID != playerID {
		return Order{}, ErrNotOrderPlayer
	}

	if err := requireTransition(Status(order.Status), target); err != nil {
		return Order{}, err
	}

	var transitionSQL string
	switch target {
	case StatusInService:
		transitionSQL = `
			UPDATE orders
			SET status = 'IN_SERVICE',
			    version = version + 1,
			    service_started_at = now(),
			    updated_at = now()
			WHERE id = $1::uuid
			RETURNING
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
		`
	case StatusFinishRequested:
		transitionSQL = `
			UPDATE orders
			SET status = 'FINISH_REQUESTED',
			    version = version + 1,
			    finish_requested_at = now(),
			    updated_at = now()
			WHERE id = $1::uuid
			RETURNING
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
		`
	default:
		return Order{}, &InvalidTransitionError{
			From: Status(order.Status),
			To:   target,
		}
	}

	updated, err := scanOrder(tx.QueryRow(ctx, transitionSQL, orderID))
	if err != nil {
		return Order{}, fmt.Errorf("update order lifecycle: %w", err)
	}

	fromStatus := order.Status
	if err := appendOrderEvidence(
		ctx,
		tx,
		orderID,
		eventType,
		&fromStatus,
		string(target),
		"PLAYER",
		playerID,
		map[string]any{},
	); err != nil {
		return Order{}, err
	}

	if err := tx.Commit(ctx); err != nil {
		return Order{}, fmt.Errorf("commit order lifecycle transition: %w", err)
	}
	return updated, nil
}

func appendOrderEvidence(
	ctx context.Context,
	tx pgx.Tx,
	orderID string,
	eventType string,
	fromStatus *string,
	toStatus string,
	actorType string,
	actorID string,
	payload map[string]any,
) error {
	eventPayload := make(map[string]any, len(payload))
	for key, value := range payload {
		eventPayload[key] = value
	}
	encodedEventPayload, err := json.Marshal(eventPayload)
	if err != nil {
		return err
	}

	eventID, err := idgen.UUIDv4()
	if err != nil {
		return err
	}
	if _, err := tx.Exec(ctx, `
		INSERT INTO order_events (
			id, order_id, event_type, from_status, to_status,
			actor_type, actor_id, payload_json, created_at
		)
		VALUES (
			$1::uuid, $2::uuid, $3, $4, $5,
			$6, NULLIF($7, ''), $8::json, clock_timestamp()
		)
	`,
		eventID,
		orderID,
		eventType,
		fromStatus,
		toStatus,
		actorType,
		actorID,
		string(encodedEventPayload),
	); err != nil {
		return fmt.Errorf("insert %s order event: %w", eventType, err)
	}

	outboxPayload := map[string]any{
		"orderId": orderID,
		"status":  toStatus,
	}
	for key, value := range payload {
		outboxPayload[key] = value
	}
	encodedOutboxPayload, err := json.Marshal(outboxPayload)
	if err != nil {
		return err
	}
	outboxID, err := idgen.UUIDv4()
	if err != nil {
		return err
	}
	if _, err := tx.Exec(ctx, `
		INSERT INTO outbox_events (
			id, aggregate_type, aggregate_id, event_type, payload_json, status,
			created_at
		)
		VALUES (
			$1::uuid, 'ORDER', $2, $3, $4::json, 'PENDING',
			clock_timestamp()
		)
	`, outboxID, orderID, eventType, string(encodedOutboxPayload)); err != nil {
		return fmt.Errorf("insert %s outbox event: %w", eventType, err)
	}
	return nil
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
		var createdAt time.Time
		if err := rows.Scan(
			&item.ID,
			&item.EventType,
			&fromStatus,
			&toStatus,
			&item.ActorType,
			&createdAt,
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
		item.CreatedAt = httpx.NewJSONTime(createdAt)
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
	requestID string,
) (authz.AuthorizationDecision, error) {
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
