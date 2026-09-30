package refunds

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/orders"
	"github.com/avaargsh/esports-companion/services/api-go/internal/platform/httpx"
	"github.com/avaargsh/esports-companion/services/api-go/internal/ports"
)

type Repository struct {
	db *pgxpool.Pool
}

type submitSnapshot struct {
	Refund       Refund
	OrderNo      string
	TotalAmount  int
	PaymentTxnID string
}

func NewRepository(db *pgxpool.Pool) Repository {
	return Repository{db: db}
}

func (r Repository) Submit(
	ctx context.Context,
	refundID string,
	provider ports.RefundProvider,
) (Refund, error) {
	snapshot, done, err := r.prepareSubmit(ctx, refundID, provider.Name())
	if err != nil {
		return Refund{}, err
	}
	if done {
		return snapshot.Refund, nil
	}

	intent, err := provider.CreateRefund(ctx, ports.RefundRequest{
		RefundID:       snapshot.Refund.ID,
		OutRefundNo:    valueOrEmpty(snapshot.Refund.OutRefundNo),
		OrderID:        snapshot.Refund.OrderID,
		OrderNo:        snapshot.OrderNo,
		PaymentTxnID:   snapshot.PaymentTxnID,
		RefundAmount:   int64(snapshot.Refund.Amount),
		TotalAmount:    int64(snapshot.TotalAmount),
		Currency:       "CNY",
		IdempotencyKey: valueOrEmpty(snapshot.Refund.OutRefundNo),
		Reason:         "Dispute refund",
	})
	if err != nil {
		return Refund{}, err
	}
	return r.applySubmitResult(ctx, refundID, provider.Name(), intent)
}

func (r Repository) prepareSubmit(
	ctx context.Context,
	refundID string,
	providerName string,
) (submitSnapshot, bool, error) {
	tx, err := r.db.Begin(ctx)
	if err != nil {
		return submitSnapshot{}, false, fmt.Errorf("begin refund submit: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	refund, rawPayload, err := scanRefundWithRaw(tx.QueryRow(ctx, `
		SELECT
			id::text,
			order_id::text,
			dispute_id::text,
			amount,
			status,
			provider,
			out_refund_no,
			provider_refund_id,
			completed_at,
			raw_payload
		FROM refunds
		WHERE id = $1::uuid
		FOR UPDATE
	`, refundID))
	if errors.Is(err, pgx.ErrNoRows) {
		return submitSnapshot{}, false, ErrRefundNotFound
	}
	if err != nil {
		return submitSnapshot{}, false, fmt.Errorf("lock refund: %w", err)
	}
	_ = rawPayload

	switch refund.Status {
	case "COMPLETED", "PROCESSING", "CLOSED", "ABNORMAL":
		return submitSnapshot{Refund: refund}, true, nil
	case "PENDING", "SUBMITTING":
	default:
		return submitSnapshot{}, false, ErrRefundNotSubmittable
	}

	var (
		orderNo     string
		orderStatus string
		totalAmount int
	)
	if err := tx.QueryRow(ctx, `
		SELECT order_no, status, total_amount
		FROM orders
		WHERE id = $1::uuid
		FOR UPDATE
	`, refund.OrderID).Scan(&orderNo, &orderStatus, &totalAmount); errors.Is(err, pgx.ErrNoRows) {
		return submitSnapshot{}, false, ErrOrderNotRefunding
	} else if err != nil {
		return submitSnapshot{}, false, fmt.Errorf("lock refund order: %w", err)
	}
	if orderStatus != string(orders.StatusRefunding) {
		return submitSnapshot{}, false, ErrOrderNotRefunding
	}

	providerUpper := strings.ToUpper(strings.TrimSpace(providerName))
	var paymentTxnID string
	var paymentErr error
	if providerUpper == "MANUAL" {
		paymentErr = tx.QueryRow(ctx, `
			SELECT provider_txn_id
			FROM payment_transactions
			WHERE order_id = $1::uuid
			  AND status = 'SUCCESS'
			ORDER BY created_at DESC
			LIMIT 1
		`, refund.OrderID).Scan(&paymentTxnID)
	} else {
		paymentErr = tx.QueryRow(ctx, `
			SELECT provider_txn_id
			FROM payment_transactions
			WHERE order_id = $1::uuid
			  AND provider = $2
			  AND status = 'SUCCESS'
			ORDER BY created_at DESC
			LIMIT 1
		`, refund.OrderID, providerUpper).Scan(&paymentTxnID)
	}
	if errors.Is(paymentErr, pgx.ErrNoRows) {
		return submitSnapshot{}, false, ErrSuccessfulPaymentNotFound
	}
	if paymentErr != nil {
		return submitSnapshot{}, false, fmt.Errorf("load successful payment: %w", paymentErr)
	}

	outRefundNo := valueOrEmpty(refund.OutRefundNo)
	if outRefundNo == "" {
		outRefundNo = "RFD_" + strings.ReplaceAll(refund.ID, "-", "")
		refund.OutRefundNo = &outRefundNo
	}
	if _, err := tx.Exec(ctx, `
		UPDATE refunds
		SET out_refund_no = $2,
		    provider = $3,
		    status = 'SUBMITTING',
		    updated_at = clock_timestamp()
		WHERE id = $1::uuid
	`, refund.ID, outRefundNo, providerUpper); err != nil {
		return submitSnapshot{}, false, fmt.Errorf("mark refund submitting: %w", err)
	}
	refund.Provider = providerUpper
	refund.Status = "SUBMITTING"

	if err := tx.Commit(ctx); err != nil {
		return submitSnapshot{}, false, fmt.Errorf("commit refund submitting: %w", err)
	}
	return submitSnapshot{
		Refund:       refund,
		OrderNo:      orderNo,
		TotalAmount:  totalAmount,
		PaymentTxnID: paymentTxnID,
	}, false, nil
}

func (r Repository) applySubmitResult(
	ctx context.Context,
	refundID string,
	expectedProvider string,
	intent ports.RefundIntent,
) (Refund, error) {
	tx, err := r.db.Begin(ctx)
	if err != nil {
		return Refund{}, fmt.Errorf("begin refund provider apply: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	refund, rawPayload, err := scanRefundWithRaw(tx.QueryRow(ctx, `
		SELECT
			id::text,
			order_id::text,
			dispute_id::text,
			amount,
			status,
			provider,
			out_refund_no,
			provider_refund_id,
			completed_at,
			raw_payload
		FROM refunds
		WHERE id = $1::uuid
		FOR UPDATE
	`, refundID))
	if errors.Is(err, pgx.ErrNoRows) {
		return Refund{}, ErrRefundNotFound
	}
	if err != nil {
		return Refund{}, fmt.Errorf("relock refund: %w", err)
	}
	if refund.Status == "COMPLETED" {
		return refund, nil
	}

	providerUpper := strings.ToUpper(strings.TrimSpace(expectedProvider))
	if strings.ToUpper(strings.TrimSpace(intent.Provider)) != providerUpper {
		return Refund{}, ErrRefundProviderMismatch
	}

	merged := map[string]any{}
	if len(rawPayload) > 0 {
		if err := json.Unmarshal(rawPayload, &merged); err != nil {
			return Refund{}, fmt.Errorf("decode refund payload: %w", err)
		}
	}
	merged["submit"] = intent.RawPayload
	encoded, err := json.Marshal(merged)
	if err != nil {
		return Refund{}, err
	}

	var providerRefundID any
	if strings.TrimSpace(intent.ProviderRefundID) != "" {
		providerRefundID = intent.ProviderRefundID
		refund.ProviderRefundID = &intent.ProviderRefundID
	}

	switch intent.Status {
	case "PENDING", "PROCESSING", "CLOSED", "ABNORMAL":
		var failureReason any
		if intent.Status == "CLOSED" || intent.Status == "ABNORMAL" {
			failureReason = "PROVIDER_REFUND_" + intent.Status
		}
		if _, err := tx.Exec(ctx, `
			UPDATE refunds
			SET provider = $2,
			    provider_refund_id = $3,
			    raw_payload = $4::json,
			    status = $5,
			    failure_reason = $6,
			    updated_at = clock_timestamp()
			WHERE id = $1::uuid
		`,
			refund.ID,
			providerUpper,
			providerRefundID,
			string(encoded),
			intent.Status,
			failureReason,
		); err != nil {
			return Refund{}, fmt.Errorf("apply refund provider result: %w", err)
		}
		refund.Provider = providerUpper
		refund.Status = intent.Status
		if err := tx.Commit(ctx); err != nil {
			return Refund{}, fmt.Errorf("commit refund provider result: %w", err)
		}
		return refund, nil
	case "SUCCESS":
		return r.completeInTx(
			ctx,
			tx,
			refund,
			providerUpper,
			intent.ProviderRefundID,
			encoded,
		)
	default:
		return Refund{}, ErrWeChatRefundStatusInvalid
	}
}

func (r Repository) completeInTx(
	ctx context.Context,
	tx pgx.Tx,
	refund Refund,
	provider string,
	providerRefundID string,
	rawPayload []byte,
) (Refund, error) {
	if strings.TrimSpace(providerRefundID) == "" {
		return Refund{}, ErrWeChatRefundInvalidResponse
	}

	var (
		disputeStatus string
		orderStatus   string
	)
	if err := tx.QueryRow(ctx, `
		SELECT status
		FROM disputes
		WHERE id = $1::uuid
		FOR UPDATE
	`, refund.DisputeID).Scan(&disputeStatus); err != nil {
		return Refund{}, fmt.Errorf("lock refund dispute: %w", err)
	}
	if err := tx.QueryRow(ctx, `
		SELECT status
		FROM orders
		WHERE id = $1::uuid
		FOR UPDATE
	`, refund.OrderID).Scan(&orderStatus); err != nil {
		return Refund{}, fmt.Errorf("lock refund completion order: %w", err)
	}
	if orderStatus != string(orders.StatusRefunding) {
		return Refund{}, ErrOrderNotRefunding
	}
	if err := orders.RequireTransition(orders.Status(orderStatus), orders.StatusRefunded); err != nil {
		return Refund{}, err
	}

	now := time.Now().UTC()
	if _, err := tx.Exec(ctx, `
		UPDATE refunds
		SET provider = $2,
		    provider_refund_id = $3,
		    raw_payload = $4::json,
		    status = 'COMPLETED',
		    failure_reason = NULL,
		    completed_at = $5,
		    updated_at = $5
		WHERE id = $1::uuid
	`,
		refund.ID,
		provider,
		providerRefundID,
		string(rawPayload),
		now,
	); err != nil {
		return Refund{}, fmt.Errorf("complete refund: %w", err)
	}
	if _, err := tx.Exec(ctx, `
		UPDATE disputes
		SET status = 'RESOLVED',
		    resolution = 'REFUND_CUSTOMER',
		    resolved_by_user_id = NULL,
		    resolved_at = $2,
		    updated_at = $2
		WHERE id = $1::uuid
	`, refund.DisputeID, now); err != nil {
		return Refund{}, fmt.Errorf("resolve refund dispute: %w", err)
	}
	if _, err := tx.Exec(ctx, `
		UPDATE orders
		SET status = 'REFUNDED',
		    version = version + 1,
		    updated_at = $2
		WHERE id = $1::uuid
	`, refund.OrderID, now); err != nil {
		return Refund{}, fmt.Errorf("mark order refunded: %w", err)
	}

	fromStatus := string(orders.StatusRefunding)
	if err := orders.AppendEvidence(
		ctx,
		tx,
		refund.OrderID,
		"REFUND_COMPLETED",
		&fromStatus,
		string(orders.StatusRefunded),
		"PAYMENT",
		"",
		map[string]any{
			"disputeId":       refund.DisputeID,
			"refundId":        refund.ID,
			"providerRefundId": providerRefundID,
			"amount":           refund.Amount,
		},
	); err != nil {
		return Refund{}, err
	}

	if err := tx.Commit(ctx); err != nil {
		return Refund{}, fmt.Errorf("commit completed refund: %w", err)
	}
	refund.Provider = provider
	refund.ProviderRefundID = &providerRefundID
	refund.Status = "COMPLETED"
	refund.CompletedAt = timePtr(now)
	_ = disputeStatus
	return refund, nil
}

func scanRefundWithRaw(row pgx.Row) (Refund, []byte, error) {
	var (
		refund            Refund
		outRefundNo       pgtype.Text
		providerRefundID  pgtype.Text
		completedAt       pgtype.Timestamptz
		rawPayload        []byte
	)
	if err := row.Scan(
		&refund.ID,
		&refund.OrderID,
		&refund.DisputeID,
		&refund.Amount,
		&refund.Status,
		&refund.Provider,
		&outRefundNo,
		&providerRefundID,
		&completedAt,
		&rawPayload,
	); err != nil {
		return Refund{}, nil, err
	}
	if outRefundNo.Valid {
		value := outRefundNo.String
		refund.OutRefundNo = &value
	}
	if providerRefundID.Valid {
		value := providerRefundID.String
		refund.ProviderRefundID = &value
	}
	if completedAt.Valid {
		refund.CompletedAt = timePtr(completedAt.Time)
	}
	return refund, rawPayload, nil
}

func timePtr(value time.Time) *httpx.JSONTime {
	result := httpx.NewJSONTime(value)
	return &result
}

func valueOrEmpty(value *string) string {
	if value == nil {
		return ""
	}
	return *value
}
