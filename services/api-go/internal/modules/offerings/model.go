package offerings

type Offering struct {
	ID            string `json:"id"`
	PlayerID      string `json:"player_id"`
	SKUID         string `json:"sku_id"`
	PriceOverride *int   `json:"price_override"`
	Description   string `json:"description"`
	Status        string `json:"status"`
}

type Upsert struct {
	PriceOverride *int
	Description   string
	Status        string
}
