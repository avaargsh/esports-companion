package outbox

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"
)

type Worker struct {
	db           *pgxpool.Pool
	redis        *redis.Client
	logger       *slog.Logger
	pollInterval time.Duration
	batchSize    int
}

type event struct {
	ID            string
	AggregateType string
	AggregateID   string
	EventType     string
	Payload       map[string]any
	CustomerID    string
	PlayerID      string
}

func New(
	db *pgxpool.Pool,
	redisClient *redis.Client,
	logger *slog.Logger,
	pollInterval time.Duration,
	batchSize int,
) *Worker {
	return &Worker{
		db:           db,
		redis:        redisClient,
		logger:       logger,
		pollInterval: pollInterval,
		batchSize:    batchSize,
	}
}

func (w *Worker) Run(ctx context.Context) error {
	ticker := time.NewTicker(w.pollInterval)
	defer ticker.Stop()

	for {
		if err := w.drain(ctx); err != nil {
			if ctx.Err() != nil {
				return nil
			}
			w.logger.Error("outbox_publish_failed", "error", err)
		}

		select {
		case <-ctx.Done():
			return nil
		case <-ticker.C:
		}
	}
}

func (w *Worker) drain(ctx context.Context) error {
	for i := 0; i < w.batchSize; i++ {
		found, err := w.publishOne(ctx)
		if err != nil {
			return err
		}
		if !found {
			return nil
		}
	}
	return nil
}

func (w *Worker) publishOne(ctx context.Context) (bool, error) {
	tx, err := w.db.Begin(ctx)
	if err != nil {
		return false, fmt.Errorf("begin outbox publish: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	item, found, err := loadOne(ctx, tx)
	if err != nil || !found {
		return found, err
	}

	message, err := json.Marshal(buildMessage(item))
	if err != nil {
		return false, fmt.Errorf("encode outbox event %s: %w", item.ID, err)
	}

	channels := []string{orderChannel(item.AggregateID)}
	if item.CustomerID != "" {
		channels = append(channels, userChannel(item.CustomerID))
	}
	for _, channel := range channels {
		if err := w.redis.Publish(ctx, channel, string(message)).Err(); err != nil {
			return false, fmt.Errorf(
				"publish outbox event %s to %s: %w",
				item.ID,
				channel,
				err,
			)
		}
	}

	if _, err := tx.Exec(ctx, `
		UPDATE outbox_events
		SET status = 'PUBLISHED',
		    published_at = clock_timestamp()
		WHERE id = $1::uuid
		  AND status = 'PENDING'
	`, item.ID); err != nil {
		return false, fmt.Errorf("mark outbox event %s published: %w", item.ID, err)
	}

	if err := tx.Commit(ctx); err != nil {
		return false, fmt.Errorf("commit outbox event %s: %w", item.ID, err)
	}
	w.logger.Debug(
		"outbox_event_published",
		"event_id", item.ID,
		"event_type", item.EventType,
		"aggregate_type", item.AggregateType,
		"aggregate_id", item.AggregateID,
		"channels", channels,
	)
	return true, nil
}

func loadOne(ctx context.Context, tx pgx.Tx) (event, bool, error) {
	var (
		item       event
		payloadRaw []byte
	)
	err := tx.QueryRow(ctx, `
		SELECT
			id::text,
			aggregate_type,
			aggregate_id,
			event_type,
			payload_json
		FROM outbox_events
		WHERE status = 'PENDING'
		ORDER BY created_at, id
		FOR UPDATE SKIP LOCKED
		LIMIT 1
	`).Scan(
		&item.ID,
		&item.AggregateType,
		&item.AggregateID,
		&item.EventType,
		&payloadRaw,
	)
	if err == pgx.ErrNoRows {
		return event{}, false, nil
	}
	if err != nil {
		return event{}, false, fmt.Errorf("load pending outbox event: %w", err)
	}
	if err := json.Unmarshal(payloadRaw, &item.Payload); err != nil {
		return event{}, false, fmt.Errorf("decode outbox event %s: %w", item.ID, err)
	}

	if item.AggregateType == "ORDER" {
		if err := tx.QueryRow(ctx, `
			SELECT user_id::text
			FROM orders
			WHERE id::text = $1
		`, item.AggregateID).Scan(&item.CustomerID); err != nil && err != pgx.ErrNoRows {
			return event{}, false, fmt.Errorf("load outbox order customer: %w", err)
		}

		if err := tx.QueryRow(ctx, `
			SELECT p.user_id::text
			FROM order_assignments a
			JOIN player_profiles p ON p.id = a.player_id
			WHERE a.order_id::text = $1
			  AND a.status = 'ACTIVE'
			ORDER BY a.created_at DESC
			LIMIT 1
		`, item.AggregateID).Scan(&item.PlayerID); err != nil && err != pgx.ErrNoRows {
			return event{}, false, fmt.Errorf("load outbox active player: %w", err)
		}
	}
	return item, true, nil
}

func buildMessage(item event) map[string]any {
	messageType := "order.status_changed"
	if item.EventType == "ORDER_MESSAGE_CREATED" {
		messageType = "order.message_created"
	}
	message := map[string]any{
		"type":      messageType,
		"eventId":   item.ID,
		"eventType": item.EventType,
	}
	for key, value := range item.Payload {
		message[key] = value
	}
	return message
}

func orderChannel(orderID string) string {
	return "realtime:order:" + orderID
}

func userChannel(userID string) string {
	return "realtime:user:" + userID
}
