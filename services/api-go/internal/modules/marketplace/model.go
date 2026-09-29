package marketplace

type Offering struct {
	ID              string `json:"id"`
	SKUID           string `json:"sku_id"`
	GameID          string `json:"game_id"`
	GameName        string `json:"game_name"`
	SKUName         string `json:"sku_name"`
	ServiceType     string `json:"service_type"`
	DurationMinutes int    `json:"duration_minutes"`
	Price           int    `json:"price"`
	Description     string `json:"description"`
}

type Skill struct {
	ID          string `json:"id"`
	GameID      string `json:"game_id"`
	GameName    string `json:"game_name"`
	Rank        string `json:"rank"`
	Description string `json:"description"`
}

type Review struct {
	ID      string `json:"id"`
	Rating  int    `json:"rating"`
	Content string `json:"content"`
}

type Player struct {
	ID            string     `json:"id"`
	DisplayName   string     `json:"display_name"`
	AvatarURL     *string    `json:"avatar_url"`
	Bio           string     `json:"bio"`
	Gender        *string    `json:"gender"`
	ServiceStatus string     `json:"service_status"`
	Rating        float64    `json:"rating"`
	ReviewCount   int        `json:"review_count"`
	OrderCount    int        `json:"order_count"`
	Offerings     []Offering `json:"offerings"`
	Skills        []Skill    `json:"skills"`
	Reviews       []Review   `json:"reviews"`
}

type ListQuery struct {
	GameID *string
	Rank   *string
	Limit  int
}
