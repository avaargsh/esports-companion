package refunds

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"

	"github.com/jackc/pgx/v5"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/orders"
	"github.com/avaargsh/esports-companion/services/api-go/internal/ports"
)

type refundAggregate struct {
	Refund       Refund
	RawPayload   []byte
	OrderNo      string
	OrderStatus  string
	TotalAmount  int
	PaymentTxnID string
}

func (r Repository) Reconcile(
	ctx context.Context,
	refundID string,
	provider ports.RefundProvider,
) (Refund, error) {
	if strings.EqualFold(provider.Name(), "MANUAL") {
		return Refund{}, ErrRefundProviderQueryUnsupported
	}

	snapshot, done, err := r.prepareReconcile(ctx, refundID, provider.Name())
	if err != nil {
		return Refund{}, err
	}
	if done {
		return snapshot.Refund, nil
	}

	intent, err := provider.QueryRefund(ctx, valueOrEmpty(snapshot.Refund.OutRefundNo))
	if err != nil {
		return Refund{}, err
	}
	return r.applyReconcileResult(ctx, refundID, provider.Name(), intent)
}

func (r Repository) prepareReconcile(
	ctx context.Context,
	refundID string,
	providerName string,
) (refundAggregate, bool, error) {
	tx, err := r.db.Begin(ctx)
	if err != nil {
		return refundAggregate{}, false, fmt.Errorf("begin refund reconcile: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	aggregate, err := loadRefundAggregate(ctx, tx, refundID, true)
	if err != nil {
		return refundAggregate{}, false, err
	}
	if aggregate.Refund.Status == "COMPLETED" {
		return aggregate, true, nil
	}
	switch aggregate.Refund.Status {
	case "SUBMITTING", "PROCESSING", "CLOSED", "ABNORMAL":
	default:
		return refundAggregate{}, false, ErrRefundNotReconcilable
	}
	providerUpper := strings.ToUpper(strings.TrimSpace(providerName))
	if aggregate.Refund.Provider != providerUpper {
		return refundAggregate{}, false, ErrRefundProviderMismatch
	}
	if valueOrEmpty(aggregate.Refund.OutRefundNo) == "" {
		return refundAggregate{}, false, ErrRefundOutRefundNoMissing
	}
	if aggregate.OrderStatus != string(orders.StatusRefunding) {
		return refundAggregate{}, false, ErrOrderNotRefunding
	}

	paymentTxnID, err := successfulPaymentTxn(
		ctx,
		tx,
		aggregate.Refund.OrderID,
		providerUpper,
	)
	if err != nil {
		return refundAggregate{}, false, err
	}
	aggregate.PaymentTxnID = paymentTxnID

	if err := tx.Commit(ctx); err != nil {
		return refundAggregate{}, false, fmt.Errorf("commit refund reconcile snapshot: %w", err)
	}
	return aggregate, false, nil
}

func (r Repository) applyReconcileResult(
	ctx context.Context,
	refundID string,
	expectedProvider string,
	intent ports.RefundIntent,
) (Refund, error) {
	tx, err := r.db.Begin(ctx)
	if err != nil {
		return Refund{}, fmt.Errorf("begin reconcile apply: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	aggregate, err := loadRefundAggregate(ctx, tx, refundID, true)
	if err != nil {
		return Refund{}, err
	}
	if aggregate.Refund.Status == "COMPLETED" {
		return aggregate.Refund, nil
	}
	if aggregate.OrderStatus != string(orders.StatusRefunding) {
		return Refund{}, ErrOrderNotRefunding
	}

	providerUpper := strings.ToUpper(strings.TrimSpace(expectedProvider))
	if strings.ToUpper(strings.TrimSpace(intent.Provider)) != providerUpper {
		return Refund{}, ErrRefundProviderMismatch
	}
	if aggregate.Refund.Provider != providerUpper {
		return Refund{}, ErrRefundProviderMismatch
	}
	if existing := valueOrEmpty(aggregate.Refund.ProviderRefundID); existing != "" &&
		intent.ProviderRefundID != "" && existing != intent.ProviderRefundID {
		return Refund{}, ErrRefundProviderIDMismatch
	}

	paymentTxnID, err := successfulPaymentTxn(
		ctx,
		tx,
		aggregate.Refund.OrderID,
		providerUpper,
	)
	if err != nil {
		return Refund{}, err
	}
	aggregate.PaymentTxnID = paymentTxnID
	if err := validateQueryIntent(aggregate, intent); err != nil {
		return Refund{}, err
	}

	encoded, err := mergeRefundRaw(aggregate.RawPayload, "query", intent.RawPayload)
	if err != nil {
		return Refund{}, err
	}

	if intent.Status == "SUCCESS" {
		return r.completeInTx(
			ctx,
			tx,
			aggregate.Refund,
			providerUpper,
			intent.ProviderRefundID,
			encoded,
		)
	}
	switch intent.Status {
	case "PROCESSING", "CLOSED", "ABNORMAL":
	default:
		return Refund{}, ErrWeChatRefundStatusInvalid
	}

	var providerRefundID any
	if strings.TrimSpace(intent.ProviderRefundID) != "" {
		providerRefundID = intent.ProviderRefundID
		aggregate.Refund.ProviderRefundID = &intent.ProviderRefundID
	}
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
		aggregate.Refund.ID,
		providerUpper,
		providerRefundID,
		string(encoded),
		intent.Status,
		failureReason,
	); err != nil {
		return Refund{}, fmt.Errorf("apply refund reconcile result: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		return Refund{}, fmt.Errorf("commit refund reconcile result: %w", err)
	}
	aggregate.Refund.Provider = providerUpper
	aggregate.Refund.Status = intent.Status
	return aggregate.Refund, nil
}

func (r Repository) ApplyCallback(
	ctx context.Context,
	callback ports.RefundCallback,
) (Refund, error) {
	tx, err := r.db.Begin(ctx)
	if err != nil {
		return Refund{}, fmt.Errorf("begin refund callback apply: %w", err)
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
		WHERE out_refund_no = $1
		FOR UPDATE
	`, callback.OutRefundNo))
	if errors.Is(err, pgx.ErrNoRows) {
		return Refund{}, ErrRefundNotFound
	}
	if err != nil {
		return Refund{}, fmt.Errorf("lock callback refund: %w", err)
	}
	if refund.Provider != "WECHAT" && refund.Provider != "MANUAL" {
		return Refund{}, ErrRefundProviderMismatch
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
		return Refund{}, ErrRefundOrderNotFound
	} else if err != nil {
		return Refund{}, fmt.Errorf("lock callback order: %w", err)
	}
	if orderNo != callback.OrderNo {
		return Refund{}, ErrRefundOrderNoMismatch
	}
	if int64(totalAmount) != callback.TotalAmount {
		return Refund{}, ErrRefundTotalAmountMismatch
	}
	if int64(refund.Amount) != callback.RefundAmount {
		return Refund{}, ErrRefundAmountMismatch
	}

	paymentTxnID, err := successfulPaymentTxn(
		ctx,
		tx,
		refund.OrderID,
		"WECHAT",
	)
	if err != nil {
		if errors.Is(err, ErrSuccessfulPaymentNotFound) {
			return Refund{}, ErrRefundPaymentTxnMismatch
		}
		return Refund{}, err
	}
	if paymentTxnID != callback.PaymentTxnID {
		return Refund{}, ErrRefundPaymentTxnMismatch
	}
	if existing := valueOrEmpty(refund.ProviderRefundID); existing != "" &&
		existing != callback.ProviderRefundID {
		return Refund{}, ErrRefundProviderIDMismatch
	}

	encoded, err := mergeRefundRaw(
		rawPayload,
		"callback",
		callback.RawEvent,
	)
	if err != nil {
		return Refund{}, err
	}
	var merged map[string]any
	if err := json.Unmarshal(encoded, &merged); err != nil {
		return Refund{}, err
	}
	merged["verifiedResource"] = callback.Resource
	encoded, err = json.Marshal(merged)
	if err != nil {
		return Refund{}, err
	}

	if callback.RefundStatus == "SUCCESS" {
		if refund.Status == "COMPLETED" {
			return refund, nil
		}
		if orderStatus != string(orders.StatusRefunding) {
			return Refund{}, ErrOrderNotRefunding
		}
		return r.completeInTx(
			ctx,
			tx,
			refund,
			"WECHAT",
			callback.ProviderRefundID,
			encoded,
		)
	}
	switch callback.RefundStatus {
	case "ABNORMAL", "CLOSED":
	default:
		return Refund{}, ErrWeChatRefundCallbackStatusMismatch
	}

	if _, err := tx.Exec(ctx, `
		UPDATE refunds
		SET provider = 'WECHAT',
		    provider_refund_id = $2,
		    raw_payload = $3::json,
		    status = $4,
		    failure_reason = $5,
		    updated_at = clock_timestamp()
		WHERE id = $1::uuid
	`,
		refund.ID,
		callback.ProviderRefundID,
		string(encoded),
		callback.RefundStatus,
		"PROVIDER_REFUND_"+callback.RefundStatus,
	); err != nil {
		return Refund{}, fmt.Errorf("apply non-success refund callback: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		return Refund{}, fmt.Errorf("commit refund callback: %w", err)
	}
	refund.Provider = "WECHAT"
	refund.ProviderRefundID = &callback.ProviderRefundID
	refund.Status = callback.RefundStatus
	return refund, nil
}

func loadRefundAggregate(
	ctx context.Context,
	tx pgx.Tx,
	refundID string,
	lock bool,
) (refundAggregate, error) {
	query := `
		SELECT
			r.id::text,
			r.order_id::text,
			r.dispute_id::text,
			r.amount,
			r.status,
			r.provider,
			r.out_refund_no,
			r.provider_refund_id,
			r.completed_at,
			r.raw_payload,
			o.order_no,
			o.status,
			o.total_amount
		FROM refunds r
		JOIN orders o ON o.id = r.order_id
		WHERE r.id = $1::uuid
	`
	if lock {
		query += " FOR UPDATE OF r, o"
	}
	row := tx.QueryRow(ctx, query, refundID)
	var aggregate refundAggregate
	var raw []byte
	var outRefundNo, providerRefundID pgx.NullString
	_ = outRefundNo
	_ = providerRefundID
	refund, rawPayload, err := scanRefundAggregateRow(row, &aggregate)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return refundAggregate{}, ErrRefundNotFound
		}
		return refundAggregate{}, fmt.Errorf("load refund aggregate: %w", err)
	}
	aggregate.Refund = refund
	aggregate.RawPayload = rawPayload
	_ = raw
	return aggregate, nil
}

func scanRefundAggregateRow(
	row pgx.Row,
	aggregate *refundAggregate,
) (Refund, []byte, error) {
	var (
		refund           Refund
		outRefundNo      pgx.NullString
		providerRefundID pgx.NullString
		completedAt      pgx.NullTime
		rawPayload       []byte
	)
	err := row.Scan(
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
		&aggregate.OrderNo,
		&aggregate.OrderStatus,
		&aggregate.TotalAmount,
	)
	if err != nil {
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

func successfulPaymentTxn(
	ctx context.Context,
	tx pgx.Tx,
	orderID string,
	provider string,
) (string, error) {
	var paymentTxnID string
	if err := tx.QueryRow(ctx, `
		SELECT provider_txn_id
		FROM payment_transactions
		WHERE order_id = $1::uuid
		  AND provider = $2
		  AND status = 'SUCCESS'
		ORDER BY created_at DESC
		LIMIT 1
	`, orderID, strings.ToUpper(provider)).Scan(&paymentTxnID); errors.Is(err, pgx.ErrNoRows) {
		return "", ErrSuccessfulPaymentNotFound
	} else if err != nil {
		return "", fmt.Errorf("load successful provider payment: %w", err)
	}
	return paymentTxnID, nil
}

func validateQueryIntent(
	aggregate refundAggregate,
	intent ports.RefundIntent,
) error {
	payload := intent.RawPayload
	if asString(payload["out_refund_no"]) != valueOrEmpty(aggregate.Refund.OutRefundNo) {
		return ErrRefundQueryOutRefundNoMismatch
	}
	if asString(payload["out_trade_no"]) != aggregate.OrderNo {
		return ErrRefundQueryOrderNoMismatch
	}
	if asString(payload["transaction_id"]) != aggregate.PaymentTxnID {
		return ErrRefundQueryPaymentTxnMismatch
	}
	amount, ok := payload["amount"].(map[string]any)
	if !ok {
		return ErrRefundQueryAmountMismatch
	}
	total, totalOK := jsonNumberToInt64(amount["total"])
	refundAmount, refundOK := jsonNumberToInt64(amount["refund"])
	if !totalOK || !refundOK ||
		total != int64(aggregate.TotalAmount) ||
		refundAmount != int64(aggregate.Refund.Amount) {
		return ErrRefundQueryAmountMismatch
	}
	return nil
}

func mergeRefundRaw(
	raw []byte,
	key string,
	value map[string]any,
) ([]byte, error) {
	merged := map[string]any{}
	if len(raw) > 0 {
		if err := json.Unmarshal(raw, &merged); err != nil {
			return nil, fmt.Errorf("decode refund raw payload: %w", err)
		}
	}
	merged[key] = value
	return json.Marshal(merged)
}
