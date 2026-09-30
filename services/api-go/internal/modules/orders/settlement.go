package orders

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/idgen"
)

type lockedWallet struct {
	ID               string
	AvailableBalance int
	FrozenBalance    int
	Version          int
}

type completionEvidence struct {
	EventType string
	ActorType string
	ActorID   string
	Payload   map[string]any
}

func (r Repository) ConfirmAndSettle(
	ctx context.Context,
	userID string,
	orderID string,
) (Order, error) {
	tx, err := r.db.Begin(ctx)
	if err != nil {
		return Order{}, fmt.Errorf("begin order settlement: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	order, err := lockSettlementOrder(ctx, tx, orderID)
	if err != nil {
		return Order{}, err
	}
	if order.UserID != userID {
		return Order{}, ErrOrderNotOwned
	}
	if Status(order.Status) == StatusSettled {
		return order, nil
	}
	if Status(order.Status) != StatusFinishRequested {
		return Order{}, ErrOrderNotAwaitingConfirm
	}

	settled, err := completeAndSettleTx(
		ctx,
		tx,
		order,
		completionEvidence{
			EventType: "USER_CONFIRMED_FINISH",
			ActorType: "USER",
			ActorID:   userID,
			Payload:   map[string]any{},
		},
	)
	if err != nil {
		return Order{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return Order{}, fmt.Errorf("commit order settlement: %w", err)
	}
	return settled, nil
}

func (r Repository) AutoConfirmOneDue(
	ctx context.Context,
	now time.Time,
	timeout time.Duration,
) (Order, bool, error) {
	cutoff := now.UTC().Add(-timeout)

	tx, err := r.db.Begin(ctx)
	if err != nil {
		return Order{}, false, fmt.Errorf("begin auto-confirm settlement: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	var (
		order       Order
		designated  pgxNullableText
		requestedAt time.Time
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
			finish_requested_at
		FROM orders
		WHERE status = 'FINISH_REQUESTED'
		  AND finish_requested_at IS NOT NULL
		  AND finish_requested_at <= $1
		ORDER BY finish_requested_at, id
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
		&requestedAt,
	)
	if errors.Is(err, pgx.ErrNoRows) {
		return Order{}, false, nil
	}
	if err != nil {
		return Order{}, false, fmt.Errorf("lock due auto-confirm order: %w", err)
	}
	if designated.Valid {
		value := designated.String
		order.DesignatedPlayerID = &value
	}

	settled, err := completeAndSettleTx(
		ctx,
		tx,
		order,
		completionEvidence{
			EventType: "AUTO_CONFIRM_FINISH",
			ActorType: "SYSTEM",
			Payload: map[string]any{
				"finishRequestedAt": pythonISOTime(requestedAt),
				"timeoutSeconds":    int(timeout / time.Second),
			},
		},
	)
	if err != nil {
		return Order{}, false, err
	}
	if err := tx.Commit(ctx); err != nil {
		return Order{}, false, fmt.Errorf("commit auto-confirm settlement: %w", err)
	}
	return settled, true, nil
}

func lockSettlementOrder(
	ctx context.Context,
	tx pgx.Tx,
	orderID string,
) (Order, error) {
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
		return Order{}, fmt.Errorf("lock settlement order: %w", err)
	}
	return order, nil
}

func completeAndSettleTx(
	ctx context.Context,
	tx pgx.Tx,
	order Order,
	evidence completionEvidence,
) (Order, error) {
	if Status(order.Status) != StatusFinishRequested {
		return Order{}, ErrOrderNotAwaitingConfirm
	}
	if err := requireTransition(Status(order.Status), StatusCompleted); err != nil {
		return Order{}, err
	}

	completed, err := scanOrder(tx.QueryRow(ctx, `
		UPDATE orders
		SET status = 'COMPLETED',
		    version = version + 1,
		    completed_at = clock_timestamp(),
		    updated_at = clock_timestamp()
		WHERE id = $1::uuid
		  AND status = 'FINISH_REQUESTED'
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
	`, order.ID))
	if err != nil {
		return Order{}, fmt.Errorf("complete order before settlement: %w", err)
	}

	fromFinish := string(StatusFinishRequested)
	payload := evidence.Payload
	if payload == nil {
		payload = map[string]any{}
	}
	if err := appendOrderEvidence(
		ctx,
		tx,
		order.ID,
		evidence.EventType,
		&fromFinish,
		string(StatusCompleted),
		evidence.ActorType,
		evidence.ActorID,
		payload,
	); err != nil {
		return Order{}, err
	}

	var playerID string
	if err := tx.QueryRow(ctx, `
		SELECT player_id::text
		FROM order_assignments
		WHERE order_id = $1::uuid
		  AND status = 'ACTIVE'
		ORDER BY created_at DESC
		LIMIT 1
	`, order.ID).Scan(&playerID); errors.Is(err, pgx.ErrNoRows) {
		return Order{}, ErrAssignmentNotFound
	} else if err != nil {
		return Order{}, fmt.Errorf("load settlement assignment: %w", err)
	}

	var playerUserID string
	if err := tx.QueryRow(ctx, `
		SELECT user_id::text
		FROM player_profiles
		WHERE id = $1::uuid
	`, playerID).Scan(&playerUserID); errors.Is(err, pgx.ErrNoRows) {
		return Order{}, ErrSettlementPlayerMissing
	} else if err != nil {
		return Order{}, fmt.Errorf("load settlement player: %w", err)
	}

	var platformUserID string
	if err := tx.QueryRow(ctx, `
		SELECT id::text
		FROM users
		WHERE role = 'PLATFORM'
		ORDER BY created_at, id
		LIMIT 1
	`).Scan(&platformUserID); errors.Is(err, pgx.ErrNoRows) {
		return Order{}, ErrPlatformAccountMissing
	} else if err != nil {
		return Order{}, fmt.Errorf("load platform account: %w", err)
	}

	playerWallet, err := ensureLockedWallet(ctx, tx, playerUserID)
	if err != nil {
		return Order{}, err
	}
	platformWallet, err := ensureLockedWallet(ctx, tx, platformUserID)
	if err != nil {
		return Order{}, err
	}

	settlementID, err := idgen.UUIDv4()
	if err != nil {
		return Order{}, err
	}
	if _, err := tx.Exec(ctx, `
		INSERT INTO settlements (
			id,
			order_id,
			player_id,
			gross_amount,
			player_amount,
			platform_fee,
			status,
			idempotency_key,
			completed_at
		)
		VALUES (
			$1::uuid,
			$2::uuid,
			$3::uuid,
			$4,
			$5,
			$6,
			'COMPLETED',
			$7,
			clock_timestamp()
		)
	`,
		settlementID,
		order.ID,
		playerID,
		completed.TotalAmount,
		completed.PlayerAmount,
		completed.PlatformFee,
		fmt.Sprintf("order:%s:settlement", order.ID),
	); err != nil {
		return Order{}, fmt.Errorf("insert settlement: %w", err)
	}

	playerBalance, err := creditWallet(
		ctx,
		tx,
		playerWallet.ID,
		completed.PlayerAmount,
	)
	if err != nil {
		return Order{}, fmt.Errorf("credit player wallet: %w", err)
	}
	platformBalance, err := creditWallet(
		ctx,
		tx,
		platformWallet.ID,
		completed.PlatformFee,
	)
	if err != nil {
		return Order{}, fmt.Errorf("credit platform wallet: %w", err)
	}

	if err := insertLedger(
		ctx,
		tx,
		playerWallet.ID,
		order.ID,
		"PROVIDER_INCOME",
		completed.PlayerAmount,
		playerBalance,
	); err != nil {
		return Order{}, err
	}
	if err := insertLedger(
		ctx,
		tx,
		platformWallet.ID,
		order.ID,
		"PLATFORM_FEE",
		completed.PlatformFee,
		platformBalance,
	); err != nil {
		return Order{}, err
	}

	if err := requireTransition(Status(completed.Status), StatusSettled); err != nil {
		return Order{}, err
	}
	settled, err := scanOrder(tx.QueryRow(ctx, `
		UPDATE orders
		SET status = 'SETTLED',
		    version = version + 1,
		    settled_at = clock_timestamp(),
		    updated_at = clock_timestamp()
		WHERE id = $1::uuid
		  AND status = 'COMPLETED'
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
	`, order.ID))
	if err != nil {
		return Order{}, fmt.Errorf("settle order: %w", err)
	}

	fromCompleted := string(StatusCompleted)
	if err := appendOrderEvidence(
		ctx,
		tx,
		order.ID,
		"SETTLEMENT_COMPLETED",
		&fromCompleted,
		string(StatusSettled),
		"SYSTEM",
		"",
		map[string]any{
			"playerAmount": completed.PlayerAmount,
			"platformFee":  completed.PlatformFee,
		},
	); err != nil {
		return Order{}, err
	}
	return settled, nil
}

type pgxNullableText struct {
	String string
	Valid  bool
}

func (value *pgxNullableText) Scan(src any) error {
	if src == nil {
		value.String = ""
		value.Valid = false
		return nil
	}
	switch typed := src.(type) {
	case string:
		value.String = typed
	case []byte:
		value.String = string(typed)
	default:
		return fmt.Errorf("cannot scan %T into nullable text", src)
	}
	value.Valid = true
	return nil
}

func pythonISOTime(value time.Time) string {
	value = value.UTC().Truncate(time.Microsecond)
	if value.Nanosecond() == 0 {
		return value.Format("2006-01-02T15:04:05+00:00")
	}
	return value.Format("2006-01-02T15:04:05.000000+00:00")
}

func ensureLockedWallet(
	ctx context.Context,
	tx pgx.Tx,
	userID string,
) (lockedWallet, error) {
	walletID, err := idgen.UUIDv4()
	if err != nil {
		return lockedWallet{}, err
	}
	if _, err := tx.Exec(ctx, `
		INSERT INTO wallets (
			id,
			user_id,
			available_balance,
			frozen_balance,
			version
		)
		VALUES ($1::uuid, $2::uuid, 0, 0, 0)
		ON CONFLICT (user_id) DO NOTHING
	`, walletID, userID); err != nil {
		return lockedWallet{}, fmt.Errorf("ensure wallet: %w", err)
	}

	var wallet lockedWallet
	if err := tx.QueryRow(ctx, `
		SELECT
			id::text,
			available_balance,
			frozen_balance,
			version
		FROM wallets
		WHERE user_id = $1::uuid
		FOR UPDATE
	`, userID).Scan(
		&wallet.ID,
		&wallet.AvailableBalance,
		&wallet.FrozenBalance,
		&wallet.Version,
	); err != nil {
		return lockedWallet{}, fmt.Errorf("lock wallet: %w", err)
	}
	return wallet, nil
}

func creditWallet(
	ctx context.Context,
	tx pgx.Tx,
	walletID string,
	amount int,
) (int, error) {
	var balance int
	if err := tx.QueryRow(ctx, `
		UPDATE wallets
		SET available_balance = available_balance + $2,
		    version = version + 1,
		    updated_at = clock_timestamp()
		WHERE id = $1::uuid
		RETURNING available_balance
	`, walletID, amount).Scan(&balance); err != nil {
		return 0, err
	}
	return balance, nil
}

func insertLedger(
	ctx context.Context,
	tx pgx.Tx,
	walletID string,
	orderID string,
	entryType string,
	amount int,
	balanceAfter int,
) error {
	entryID, err := idgen.UUIDv4()
	if err != nil {
		return err
	}
	if _, err := tx.Exec(ctx, `
		INSERT INTO ledger_entries (
			id,
			account_id,
			biz_type,
			biz_id,
			entry_type,
			amount,
			balance_after
		)
		VALUES (
			$1::uuid,
			$2::uuid,
			'ORDER_SETTLEMENT',
			$3,
			$4,
			$5,
			$6
		)
	`,
		entryID,
		walletID,
		orderID,
		entryType,
		amount,
		balanceAfter,
	); err != nil {
		return fmt.Errorf("insert %s ledger entry: %w", entryType, err)
	}
	return nil
}
