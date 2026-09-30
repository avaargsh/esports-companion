package orders

import (
	"context"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"

	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/idgen"
)

type lockedWallet struct {
	ID               string
	AvailableBalance int
	FrozenBalance    int
	Version          int
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
	if order.UserID != userID {
		return Order{}, ErrOrderNotOwned
	}
	if Status(order.Status) == StatusSettled {
		return order, nil
	}
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
		    completed_at = now(),
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
	`, orderID))
	if err != nil {
		return Order{}, fmt.Errorf("complete order before settlement: %w", err)
	}
	fromFinish := string(StatusFinishRequested)
	if err := appendOrderEvidence(
		ctx,
		tx,
		orderID,
		"USER_CONFIRMED_FINISH",
		&fromFinish,
		string(StatusCompleted),
		"USER",
		userID,
		map[string]any{},
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
	`, orderID).Scan(&playerID); errors.Is(err, pgx.ErrNoRows) {
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
			now()
		)
	`,
		settlementID,
		orderID,
		playerID,
		completed.TotalAmount,
		completed.PlayerAmount,
		completed.PlatformFee,
		fmt.Sprintf("order:%s:settlement", orderID),
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
		orderID,
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
		orderID,
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
		    settled_at = now(),
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
	`, orderID))
	if err != nil {
		return Order{}, fmt.Errorf("settle order: %w", err)
	}

	fromCompleted := string(StatusCompleted)
	if err := appendOrderEvidence(
		ctx,
		tx,
		orderID,
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

	if err := tx.Commit(ctx); err != nil {
		return Order{}, fmt.Errorf("commit order settlement: %w", err)
	}
	return settled, nil
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
		    updated_at = now()
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
