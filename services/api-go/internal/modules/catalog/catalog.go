package catalog

type Game struct {
	ID      string  `json:"id"`
	Code    string  `json:"code"`
	Name    string  `json:"name"`
	IconURL *string `json:"icon_url"`
}

type SKU struct {
	ID              string `json:"id"`
	GameID          string `json:"game_id"`
	Name            string `json:"name"`
	ServiceType     string `json:"service_type"`
	DurationMinutes int    `json:"duration_minutes"`
	Price           int    `json:"price"`
}
