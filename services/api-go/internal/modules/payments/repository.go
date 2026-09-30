package payments

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/orders"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/idgen"
	"github.com/avaargsh/esports-companion/services/api-go/internal/ports"
)

type scanner interface {
	Scan(...any) error
}

type Repository struct {
	db *pgxpool.Pool
}

func NewRepository(db *pgxpool.Pool) Repository {
	return Repository{db: db}
}

func (r Repository) Pay(
	ctx context.Context,
	userID string,
	orderID string,
	idempotencyKey string,
	provider ports.PaymentProvider,
) (orders.Order, error) {
	tx, err := r.db.Begin(ctx)
	if err != nil {
		return orders.Order{}, fmt.Errorf("begin payment transaction: %w", err)
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
		return orders.Order{}, orders.ErrOrderNotFound
	}
	if err != nil {
		return orders.Order{}, fmt.Errorf("lock payment order: %w", err)
	}
	if order.UserID != userID {
		return orders.Order{}, orders.ErrOrderNotOwned
	}

	var existingOrderID string
	err = tx.QueryRow(ctx, `
		SELECT order_id::text
		FROM payment_transactions
		WHERE idempotency_key = $1
	`, idempotencyKey).Scan(&existingOrderID)
	switch {
	case err == nil:
		if existingOrderID != order.ID {
			return orders.Order{}, ErrIdempotencyKeyReused
		}
		return order, nil
	case !errors.Is(err, pgx.ErrNoRows):
		return orders.Order{}, fmt.Errorf("load payment idempotency key: %w", err)
	}

	if orders.Status(order.Status) != orders.StatusWaitingPayment {
		return orders.Order{}, ErrOrderNotWaitingPayment
	}

	var pending bool
	if err := tx.QueryRow(ctx, `
		SELECT EXISTS(
			SELECT 1
			FROM payment_transactions
			WHERE order_id = $1::uuid
			  AND provider = 'MOCK'
			  AND status = 'PENDING'
		)
	`, orderID).Scan(&pending); err != nil {
		return orders.Order{}, fmt.Errorf("check pending payment: %w", err)
	}
	if pending {
		return orders.Order{}, ErrPaymentAttemptExists
	}

	var payerExists bool
	if err := tx.QueryRow(ctx, `
		SELECT EXISTS(
			SELECT 1
			FROM users
			WHERE id = $1::uuid
		)
	`, order.UserID).Scan(&payerExists); err != nil {
		return orders.Order{}, fmt.Errorf("load payment payer: %w", err)
	}
	if !payerExists {
		return orders.Order{}, ErrPaymentPayerNotFound
	}

	intent, err := provider.CreatePayment(
		ctx,
		order.ID,
		int64(order.TotalAmount),
		"CNY",
		idempotencyKey,
		"",
	)
	if err != nil {
		return orders.Order{}, err
	}
	providerName := strings.ToUpper(intent.Provider)
	if providerName != "MOCK" {
		return orders.Order{}, ErrPaymentProviderMismatch
	}
	if intent.Status != "SUCCESS" {
		return orders.Order{}, ErrPaymentProviderBadStatus
	}

	rawPayload, err := json.Marshal(map[string]any{
		"provider": map[string]any{
			"mode":           "mock",
			"idempotencyKey": idempotencyKey,
		},
		"clientPayload": map[string]any{},
	})
	if err != nil {
		return orders.Order{}, err
	}
	paymentID, err := idgen.UUIDv4()
	if err != nil {
		return orders.Order{}, err
	}
	if _, err := tx.Exec(ctx, `
		INSERT INTO payment_transactions (
			id,
			order_id,
			provider,
			provider_txn_id,
			idempotency_key,
			amount,
			status,
			raw_payload
		)
		VALUES (
			$1::uuid,
			$2::uuid,
			$3,
			$4,
			$5,
			$6,
			'SUCCESS',
			$7::json
		)
	`,
		paymentID,
		order.ID,
		providerName,
		intent.ProviderTxnID,
		idempotencyKey,
		order.TotalAmount,
		string(rawPayload),
	); err != nil {
		return orders.Order{}, fmt.Errorf("insert payment transaction: %w", err)
	}

	order, err = transitionOrder(
		ctx,
		tx,
		order,
		orders.StatusPaid,
		"PAYMENT_SUCCESS",
		"PAYMENT",
		"",
		map[string]any{"provider": providerName},
	)
	if err != nil {
		return orders.Order{}, err
	}
	order, err = transitionOrder(
		ctx,
		tx,
		order,
		orders.StatusMatching,
		"ORDER_ENTERED_MATCHING",
		"SYSTEM",
		"",
		map[string]any{},
	)
	if err != nil {
		return orders.Order{}, err
	}

	if order.DesignatedPlayerID != nil {
		order, err = assignDesignated(ctx, tx, order, userID)
		if err != nil {
			return orders.Order{}, err
		}
	}

	if err := tx.Commit(ctx); err != nil {
		return orders.Order{}, fmt.Errorf("commit payment transaction: %w", err)
	}
	return order, nil
}

func transitionOrder(
	ctx context.Context,
	tx pgx.Tx,
	order orders.Order,
	target orders.Status,
	eventType string,
	actorType string,
	actorID string,
	payload map[string]any,
) (orders.Order, error) {
	if err := orders.RequireTransition(orders.Status(order.Status), target); err != nil {
		return orders.Order{}, err
	}

	var statement string
	switch target {
	case orders.StatusPaid:
		statement = `
			UPDATE orders
			SET status = 'PAID',
			    version = version + 1,
			    paid_at = clock_timestamp(),
			    updated_at = clock_timestamp()
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
	case orders.StatusMatching:
		statement = `
			UPDATE orders
			SET status = 'MATCHING',
			    version = version + 1,
			    updated_at = clock_timestamp()
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
	case orders.StatusAccepted:
		statement = `
			UPDATE orders
			SET status = 'ACCEPTED',
			    version = version + 1,
			    accepted_at = clock_timestamp(),
			    updated_at = clock_timestamp()
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
		return orders.Order{}, fmt.Errorf("unsupported payment order target: %s", target)
	}

	updated, err := scanOrder(tx.QueryRow(ctx, statement, order.ID))
	if err != nil {
		return orders.Order{}, fmt.Errorf("transition payment order to %s: %w", target, err)
	}

	fromStatus := order.Status
	if err := orders.AppendEvidence(
		ctx,
		tx,
		order.ID,
		eventType,
		&fromStatus,
		string(target),
		actorType,
		actorID,
		payload,
	); err != nil {
		return orders.Order{}, err
	}
	return updated, nil
}

func assignDesignated(
	ctx context.Context,
	tx pgx.Tx,
	order orders.Order,
	userID string,
) (orders.Order, error) {
	if order.DesignatedPlayerID == nil {
		return order, nil
	}
	if orders.Status(order.Status) != orders.StatusMatching {
		return orders.Order{}, fmt.Errorf("%w: %s", orders.ErrOrderAlreadyAccepted, order.Status)
	}

	var existingPlayerID string
	err := tx.QueryRow(ctx, `
		SELECT player_id::text
		FROM order_assignments
		WHERE order_id = $1::uuid
		  AND status = 'ACTIVE'
		ORDER BY created_at DESC
		LIMIT 1
	`, order.ID).Scan(&existingPlayerID)
	switch {
	case err == nil:
		return order, nil
	case !errors.Is(err, pgx.ErrNoRows):
		return orders.Order{}, fmt.Errorf("load designated assignment: %w", err)
	}

	var playerExists bool
	if err := tx.QueryRow(ctx, `
		SELECT EXISTS(
			SELECT 1
			FROM player_profiles
			WHERE id = $1::uuid
		)
	`, *order.DesignatedPlayerID).Scan(&playerExists); err != nil {
		return orders.Order{}, fmt.Errorf("load designated player: %w", err)
	}
	if !playerExists {
		return orders.Order{}, ErrDesignatedPlayerNotFound
	}

	assignmentID, err := idgen.UUIDv4()
	if err != nil {
		return orders.Order{}, err
	}
	if _, err := tx.Exec(ctx, `
		INSERT INTO order_assignments (
			id,
			order_id,
			player_id,
			status,
			assigned_by,
			accepted_at
		)
		VALUES (
			$1::uuid,
			$2::uuid,
			$3::uuid,
			'ACTIVE',
			'USER',
			clock_timestamp()
		)
	`,
		assignmentID,
		order.ID,
		*order.DesignatedPlayerID,
	); err != nil {
		return orders.Order{}, fmt.Errorf("insert designated assignment: %w", err)
	}

	return transitionOrder(
		ctx,
		tx,
		order,
		orders.StatusAccepted,
		"DESIGNATED_PLAYER_ASSIGNED",
		"USER",
		userID,
		map[string]any{"playerId": *order.DesignatedPlayerID},
	)
}

func scanOrder(row scanner) (orders.Order, error) {
	var item orders.Order
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
		return orders.Order{}, err
	}
	if designated.Valid {
		value := designated.String
		item.DesignatedPlayerID = &value
	}
	return item, nil
}
