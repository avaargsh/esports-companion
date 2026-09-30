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

func (r Repository) Prepare(
	ctx context.Context,
	userID string,
	orderID string,
	idempotencyKey string,
	provider ports.PaymentProvider,
) (Preparation, error) {
	tx, err := r.db.Begin(ctx)
	if err != nil {
		return Preparation{}, fmt.Errorf("begin payment transaction: %w", err)
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
		return Preparation{}, orders.ErrOrderNotFound
	}
	if err != nil {
		return Preparation{}, fmt.Errorf("lock payment order: %w", err)
	}
	if order.UserID != userID {
		return Preparation{}, orders.ErrOrderNotOwned
	}

	var (
		existingOrderID  string
		existingProvider string
		existingStatus   string
		existingRaw      []byte
	)
	err = tx.QueryRow(ctx, `
		SELECT
			order_id::text,
			provider,
			status,
			raw_payload
		FROM payment_transactions
		WHERE idempotency_key = $1
	`, idempotencyKey).Scan(
		&existingOrderID,
		&existingProvider,
		&existingStatus,
		&existingRaw,
	)
	switch {
	case err == nil:
		if existingOrderID != order.ID {
			return Preparation{}, ErrIdempotencyKeyReused
		}
		clientPayload, err := storedClientPayload(existingRaw)
		if err != nil {
			return Preparation{}, err
		}
		return Preparation{
			Order:         order,
			Provider:      existingProvider,
			PaymentStatus: existingStatus,
			ClientPayload: clientPayload,
			Replayed:      true,
		}, nil
	case !errors.Is(err, pgx.ErrNoRows):
		return Preparation{}, fmt.Errorf("load payment idempotency key: %w", err)
	}

	if orders.Status(order.Status) != orders.StatusWaitingPayment {
		return Preparation{}, ErrOrderNotWaitingPayment
	}

	providerName := strings.ToUpper(strings.TrimSpace(provider.Name()))
	var pending bool
	if err := tx.QueryRow(ctx, `
		SELECT EXISTS(
			SELECT 1
			FROM payment_transactions
			WHERE order_id = $1::uuid
			  AND provider = $2
			  AND status = 'PENDING'
		)
	`, orderID, providerName).Scan(&pending); err != nil {
		return Preparation{}, fmt.Errorf("check pending payment: %w", err)
	}
	if pending {
		return Preparation{}, ErrPaymentAttemptExists
	}

	var payerOpenID pgtype.Text
	err = tx.QueryRow(ctx, `
		SELECT openid
		FROM users
		WHERE id = $1::uuid
	`, order.UserID).Scan(&payerOpenID)
	if errors.Is(err, pgx.ErrNoRows) {
		return Preparation{}, ErrPaymentPayerNotFound
	}
	if err != nil {
		return Preparation{}, fmt.Errorf("load payment payer: %w", err)
	}

	intent, err := provider.CreatePayment(ctx, ports.PaymentRequest{
		OrderID:        order.ID,
		OrderNo:        order.OrderNo,
		Description:    "Esports Companion " + order.OrderNo,
		AmountMinor:    int64(order.TotalAmount),
		Currency:       "CNY",
		IdempotencyKey: idempotencyKey,
		PayerSubject:   payerOpenID.String,
	})
	if err != nil {
		return Preparation{}, err
	}
	if strings.ToUpper(strings.TrimSpace(intent.Provider)) != providerName {
		return Preparation{}, ErrPaymentProviderMismatch
	}
	if intent.Status != "PENDING" && intent.Status != "SUCCESS" {
		return Preparation{}, ErrPaymentProviderBadStatus
	}

	rawPayload, err := json.Marshal(map[string]any{
		"provider":      intent.RawPayload,
		"clientPayload": intent.ClientPayload,
	})
	if err != nil {
		return Preparation{}, err
	}
	paymentID, err := idgen.UUIDv4()
	if err != nil {
		return Preparation{}, err
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
			$7,
			$8::json
		)
	`,
		paymentID,
		order.ID,
		providerName,
		intent.ProviderTxnID,
		idempotencyKey,
		order.TotalAmount,
		intent.Status,
		string(rawPayload),
	); err != nil {
		return Preparation{}, fmt.Errorf("insert payment transaction: %w", err)
	}

	if intent.Status == "SUCCESS" {
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
			return Preparation{}, err
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
			return Preparation{}, err
		}

		if order.DesignatedPlayerID != nil {
			order, err = assignDesignated(ctx, tx, order, userID)
			if err != nil {
				return Preparation{}, err
			}
		}
	}

	if err := tx.Commit(ctx); err != nil {
		return Preparation{}, fmt.Errorf("commit payment transaction: %w", err)
	}
	return Preparation{
		Order:         order,
		Provider:      providerName,
		PaymentStatus: intent.Status,
		ClientPayload: intent.ClientPayload,
		Replayed:      false,
	}, nil
}

func (r Repository) Pay(
	ctx context.Context,
	userID string,
	orderID string,
	idempotencyKey string,
	provider ports.PaymentProvider,
) (orders.Order, error) {
	preparation, err := r.Prepare(
		ctx,
		userID,
		orderID,
		idempotencyKey,
		provider,
	)
	if err != nil {
		return orders.Order{}, err
	}
	return preparation.Order, nil
}

func storedClientPayload(raw []byte) (map[string]string, error) {
	if len(raw) == 0 {
		return map[string]string{}, nil
	}
	var payload struct {
		ClientPayload map[string]string `json:"clientPayload"`
	}
	if err := json.Unmarshal(raw, &payload); err != nil {
		return nil, fmt.Errorf("decode payment replay payload: %w", err)
	}
	if payload.ClientPayload == nil {
		payload.ClientPayload = map[string]string{}
	}
	return payload.ClientPayload, nil
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
