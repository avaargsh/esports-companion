package realtime

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"strings"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/auth"
)

const (
	redisRealtimePattern = "realtime:*"
	reconnectDelay       = time.Second
	clientBufferSize     = 64
	clientDedupeSize     = 512
)

type client struct {
	userID string
	roles  []string
	send   chan []byte
	cancel context.CancelFunc

	seenMu    sync.Mutex
	seen      map[string]struct{}
	seenOrder []string
}

type Hub struct {
	repo   Repository
	redis  *redis.Client
	logger *slog.Logger

	mu             sync.RWMutex
	subscriptions  map[string]map[*client]struct{}
	clientChannels map[*client]map[string]struct{}
}

func NewHub(
	repo Repository,
	redisClient *redis.Client,
	logger *slog.Logger,
) *Hub {
	return &Hub{
		repo:           repo,
		redis:          redisClient,
		logger:         logger,
		subscriptions:  make(map[string]map[*client]struct{}),
		clientChannels: make(map[*client]map[string]struct{}),
	}
}

func (h *Hub) Run(ctx context.Context) {
	for ctx.Err() == nil {
		err := h.runSubscription(ctx)
		if ctx.Err() != nil {
			return
		}
		h.logger.Error("realtime_redis_subscription_failed", "error", err)
		timer := time.NewTimer(reconnectDelay)
		select {
		case <-ctx.Done():
			timer.Stop()
			return
		case <-timer.C:
		}
	}
}

func (h *Hub) runSubscription(ctx context.Context) error {
	pubsub := h.redis.PSubscribe(ctx, redisRealtimePattern)
	defer func() { _ = pubsub.Close() }()

	if _, err := pubsub.Receive(ctx); err != nil {
		return err
	}
	messages := pubsub.Channel()
	for {
		select {
		case <-ctx.Done():
			return nil
		case message, ok := <-messages:
			if !ok {
				return errors.New("REDIS_REALTIME_SUBSCRIPTION_CLOSED")
			}
			h.dispatchRedis(ctx, message.Channel, []byte(message.Payload))
		}
	}
}

func (h *Hub) newClient(
	principal auth.Principal,
	cancel context.CancelFunc,
) *client {
	return &client{
		userID: principal.User.ID,
		roles:  append([]string(nil), principal.Roles...),
		send:   make(chan []byte, clientBufferSize),
		cancel: cancel,
		seen:   make(map[string]struct{}, clientDedupeSize),
	}
}

func (h *Hub) Subscribe(current *client, channels []string) {
	h.mu.Lock()
	defer h.mu.Unlock()

	if _, ok := h.clientChannels[current]; !ok {
		h.clientChannels[current] = make(map[string]struct{})
	}
	for _, channel := range channels {
		if _, ok := h.subscriptions[channel]; !ok {
			h.subscriptions[channel] = make(map[*client]struct{})
		}
		h.subscriptions[channel][current] = struct{}{}
		h.clientChannels[current][channel] = struct{}{}
	}
}

func (h *Hub) Remove(current *client) {
	h.mu.Lock()
	defer h.mu.Unlock()

	for channel := range h.clientChannels[current] {
		clients := h.subscriptions[channel]
		delete(clients, current)
		if len(clients) == 0 {
			delete(h.subscriptions, channel)
		}
	}
	delete(h.clientChannels, current)
}

func (h *Hub) dispatchRedis(
	ctx context.Context,
	redisChannel string,
	payload []byte,
) {
	eventID := realtimeEventID(payload)
	logicalChannel := strings.TrimPrefix(redisChannel, "realtime:")
	if logicalChannel == redisChannel {
		return
	}

	var allowed map[string]struct{}
	if strings.HasPrefix(logicalChannel, "order:") {
		orderID := strings.TrimPrefix(logicalChannel, "order:")
		var err error
		allowed, err = h.repo.OrderAllowedUsers(ctx, orderID)
		if err != nil {
			h.logger.Error(
				"realtime_order_authorization_refresh_failed",
				"order_id", orderID,
				"error", err,
			)
			return
		}
	}

	h.mu.RLock()
	targets := make([]*client, 0, len(h.subscriptions[logicalChannel]))
	for current := range h.subscriptions[logicalChannel] {
		targets = append(targets, current)
	}
	h.mu.RUnlock()

	for _, current := range targets {
		if allowed != nil && !clientAllowedForOrder(current, allowed) {
			continue
		}
		if eventID != "" && !current.acceptEvent(eventID) {
			continue
		}
		copyPayload := append([]byte(nil), payload...)
		select {
		case current.send <- copyPayload:
		default:
			h.logger.Warn(
				"realtime_slow_consumer_disconnected",
				"user_id", current.userID,
				"channel", logicalChannel,
			)
			current.cancel()
		}
	}
}

func clientAllowedForOrder(
	current *client,
	allowed map[string]struct{},
) bool {
	if hasRole(current.roles, "PLATFORM") {
		return true
	}
	_, ok := allowed[current.userID]
	return ok
}

func realtimeEventID(payload []byte) string {
	var envelope struct {
		EventID string `json:"eventId"`
	}
	if err := json.Unmarshal(payload, &envelope); err != nil {
		return ""
	}
	return envelope.EventID
}

func (c *client) acceptEvent(eventID string) bool {
	c.seenMu.Lock()
	defer c.seenMu.Unlock()

	if _, exists := c.seen[eventID]; exists {
		return false
	}
	c.seen[eventID] = struct{}{}
	c.seenOrder = append(c.seenOrder, eventID)
	if len(c.seenOrder) > clientDedupeSize {
		evicted := c.seenOrder[0]
		c.seenOrder = c.seenOrder[1:]
		delete(c.seen, evicted)
	}
	return true
}
