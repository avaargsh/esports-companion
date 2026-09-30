package realtime

import (
	"context"
	"encoding/json"
	"net/http"
	"time"

	"github.com/coder/websocket"
	"github.com/coder/websocket/wsjson"
	"github.com/go-chi/chi/v5"

	"github.com/avaargsh/esports-companion/services/api-go/internal/modules/auth"
)

const websocketWriteTimeout = 10 * time.Second

type Handler struct {
	rootCtx     context.Context
	authService auth.Service
	repo        Repository
	hub         *Hub
	secure      bool
}

func NewHandler(
	rootCtx context.Context,
	authService auth.Service,
	repo Repository,
	hub *Hub,
	secure bool,
) Handler {
	return Handler{
		rootCtx:     rootCtx,
		authService: authService,
		repo:        repo,
		hub:         hub,
		secure:      secure,
	}
}

func (h Handler) Register(r chi.Router) {
	r.Get("/ws", h.serve)
}

func (h Handler) serve(w http.ResponseWriter, r *http.Request) {
	principal, requestErr := h.resolvePrincipal(r)

	conn, err := websocket.Accept(w, r, &websocket.AcceptOptions{
		// Match the current FastAPI WebSocket behavior. Authentication and
		// per-channel authorization remain mandatory.
		InsecureSkipVerify: true,
	})
	if err != nil {
		return
	}
	defer conn.CloseNow()
	conn.SetReadLimit(64 * 1024)

	if requestErr != nil {
		_ = conn.Close(websocket.StatusCode(4401), "authentication required")
		return
	}

	ctx, cancel := context.WithCancel(h.rootCtx)
	defer cancel()
	current := h.hub.newClient(principal, cancel)
	defer h.hub.Remove(current)

	writerDone := make(chan struct{})
	go h.writeLoop(ctx, cancel, conn, current, writerDone)
	defer func() {
		cancel()
		<-writerDone
	}()

	for {
		var message map[string]any
		if err := wsjson.Read(ctx, conn, &message); err != nil {
			return
		}

		messageType, _ := message["type"].(string)
		if messageType != "subscribe" {
			if !enqueueJSON(current, map[string]any{
				"type": "error",
				"code": "UNSUPPORTED_MESSAGE_TYPE",
			}) {
				return
			}
			continue
		}

		rawChannels, ok := message["channels"].([]any)
		if !ok {
			if !enqueueJSON(current, map[string]any{
				"type": "error",
				"code": "CHANNELS_REQUIRED",
			}) {
				return
			}
			continue
		}
		channels := make([]string, 0, len(rawChannels))
		for _, value := range rawChannels {
			channel, ok := value.(string)
			if !ok {
				channel = ""
			}
			channels = append(channels, channel)
		}

		accepted, rejected, err := h.repo.AuthorizeChannels(
			ctx,
			principal,
			channels,
		)
		if err != nil {
			_ = conn.Close(
				websocket.StatusInternalError,
				"channel authorization failed",
			)
			return
		}
		h.hub.Subscribe(current, accepted)
		if !enqueueJSON(current, map[string]any{
			"type":     "subscribed",
			"channels": accepted,
			"rejected": rejected,
		}) {
			return
		}
	}
}

func (h Handler) resolvePrincipal(
	r *http.Request,
) (auth.Principal, *auth.RequestError) {
	if !h.secure &&
		r.Header.Get("Authorization") == "" &&
		r.Header.Get("X-User-Id") == "" &&
		r.Header.Get("X-Admin-Id") == "" {
		if userID := r.URL.Query().Get("user_id"); userID != "" {
			r = r.Clone(r.Context())
			r.Header.Set("X-User-Id", userID)
		}
	}
	return auth.ResolvePrincipal(h.authService, h.secure, r)
}

func (h Handler) writeLoop(
	ctx context.Context,
	cancel context.CancelFunc,
	conn *websocket.Conn,
	current *client,
	done chan<- struct{},
) {
	defer close(done)
	for {
		select {
		case <-ctx.Done():
			return
		case payload := <-current.send:
			writeCtx, writeCancel := context.WithTimeout(
				ctx,
				websocketWriteTimeout,
			)
			err := conn.Write(
				writeCtx,
				websocket.MessageText,
				payload,
			)
			writeCancel()
			if err != nil {
				cancel()
				return
			}
		}
	}
}

func enqueueJSON(current *client, value any) bool {
	payload, err := json.Marshal(value)
	if err != nil {
		current.cancel()
		return false
	}
	select {
	case current.send <- payload:
		return true
	default:
		current.cancel()
		return false
	}
}
