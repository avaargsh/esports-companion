package orders

import "time"

type Order struct {
	ID                 string  `json:"id"`
	OrderNo            string  `json:"order_no"`
	UserID             string  `json:"user_id"`
	GameID             string  `json:"game_id"`
	SKUID              string  `json:"sku_id"`
	DesignatedPlayerID *string `json:"designated_player_id"`
	Status             string  `json:"status"`
	Quantity           int     `json:"quantity"`
	UnitPrice          int     `json:"unit_price"`
	TotalAmount        int     `json:"total_amount"`
	PlayerAmount       int     `json:"player_amount"`
	PlatformFee        int     `json:"platform_fee"`
	Version            int     `json:"version"`
}

type ServicePlayer struct {
	ID            string  `json:"id"`
	DisplayName   string  `json:"display_name"`
	AvatarURL     *string `json:"avatar_url"`
	Rating        float64 `json:"rating"`
	ServiceStatus string  `json:"service_status"`
	Binding       string  `json:"binding"`
	AssignedBy    *string `json:"assigned_by"`
}

type Detail struct {
	Order
	ServicePlayer    *ServicePlayer `json:"service_player"`
	AvailableActions []string       `json:"available_actions"`
}

type Event struct {
	ID         string    `json:"id"`
	EventType  string    `json:"event_type"`
	FromStatus *string   `json:"from_status"`
	ToStatus   *string   `json:"to_status"`
	ActorType  string    `json:"actor_type"`
	CreatedAt  time.Time `json:"created_at"`
}

func availableActions(status string) []string {
	switch status {
	case "WAITING_PAYMENT":
		return []string{"PAY", "CANCEL"}
	case "MATCHING":
		return []string{"REQUEST_REFUND"}
	case "ACCEPTED":
		return []string{"REQUEST_REFUND", "OPEN_DISPUTE"}
	case "IN_SERVICE", "FINISH_REQUESTED":
		return []string{"OPEN_DISPUTE"}
	default:
		return []string{}
	}
}
