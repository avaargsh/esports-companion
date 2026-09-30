package orders

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgtype"
)

type TimedOutAssignment struct {
	OrderID   string
	GameID    string
	CreatedAt time.Time
}

func (r Repository) RequeueOneTimedOutAssignment(
	ctx context.Context,
	now time.Time,
	timeout time.Duration,
) (TimedOutAssignment, bool, error) {
	cutoff := now.UTC().Add(-timeout)

	tx, err := r.db.Begin(ctx)
	if err != nil {
		return TimedOutAssignment{}, false, fmt.Errorf("begin assignment timeout: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	var (
		order      Order
		designated pgtype.Text
		acceptedAt time.Time
		createdAt  time.Time
	)
	err = tx.QueryRow(ctx, `
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
			version,
			accepted_at,
			created_at
		FROM orders
		WHERE status = 'ACCEPTED'
		  AND accepted_at IS NOT NULL
		  AND accepted_at <= $1
		ORDER BY accepted_at, id
		FOR UPDATE SKIP LOCKED
		LIMIT 1
	`, cutoff).Scan(
		&order.ID,
		&order.OrderNo,
		&order.UserID,
		&order.GameID,
		&order.SKUID,
		&designated,
		&order.Status,
		&order.Quantity,
		&order.UnitPrice,
		&order.TotalAmount,
		&order.PlayerAmount,
		&order.PlatformFee,
		&order.Version,
		&acceptedAt,
		&createdAt,
	)
	if errors.Is(err, pgx.ErrNoRows) {
		return TimedOutAssignment{}, false, nil
	}
	if err != nil {
		return TimedOutAssignment{}, false, fmt.Errorf("lock due assignment order: %w", err)
	}
	if designated.Valid {
		value := designated.String
		order.DesignatedPlayerID = &value
	}

	var (
		assignmentID pgtype.Text
		playerID     pgtype.Text
	)
	err = tx.QueryRow(ctx, `
		SELECT id::text, player_id::text
		FROM order_assignments
		WHERE order_id = $1::uuid
		  AND status = 'ACTIVE'
		ORDER BY created_at DESC
		LIMIT 1
		FOR UPDATE
	`, order.ID).Scan(&assignmentID, &playerID)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return TimedOutAssignment{}, false, fmt.Errorf("lock timed-out assignment: %w", err)
	}

	var previousPlayerID any
	if err == nil {
		if _, err := tx.Exec(ctx, `
			UPDATE order_assignments
			SET status = 'RELEASED',
			    released_at = $2,
			    updated_at = clock_timestamp()
			WHERE id = $1::uuid
			  AND status = 'ACTIVE'
		`, assignmentID.String, now.UTC()); err != nil {
			return TimedOutAssignment{}, false, fmt.Errorf("release timed-out assignment: %w", err)
		}
		previousPlayerID = playerID.String
	} else if order.DesignatedPlayerID != nil {
		previousPlayerID = *order.DesignatedPlayerID
	}

	if err := requireTransition(Status(order.Status), StatusMatching); err != nil {
		return TimedOutAssignment{}, false, err
	}
	if _, err := tx.Exec(ctx, `
		UPDATE orders
		SET status = 'MATCHING',
		    designated_player_id = NULL,
		    version = version + 1,
		    updated_at = clock_timestamp()
		WHERE id = $1::uuid
		  AND status = 'ACCEPTED'
	`, order.ID); err != nil {
		return TimedOutAssignment{}, false, fmt.Errorf("requeue timed-out order: %w", err)
	}

	fromStatus := string(StatusAccepted)
	if err := appendOrderEvidence(
		ctx,
		tx,
		order.ID,
		"ASSIGNMENT_TIMED_OUT",
		&fromStatus,
		string(StatusMatching),
		"SYSTEM",
		"",
		map[string]any{
			"playerId":       previousPlayerID,
			"timeoutSeconds": int(timeout / time.Second),
		},
	); err != nil {
		return TimedOutAssignment{}, false, err
	}

	if err := tx.Commit(ctx); err != nil {
		return TimedOutAssignment{}, false, fmt.Errorf("commit assignment timeout: %w", err)
	}
	return TimedOutAssignment{
		OrderID:   order.ID,
		GameID:    order.GameID,
		CreatedAt: createdAt.UTC(),
	}, true, nil
}
