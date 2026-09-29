export type OrderStatus =
  | "WAITING_PAYMENT"
  | "PAID"
  | "MATCHING"
  | "ACCEPTED"
  | "IN_SERVICE"
  | "FINISH_REQUESTED"
  | "COMPLETED"
  | "SETTLED"
  | "CANCELLED"
  | "REFUNDING"
  | "REFUNDED"
  | "DISPUTED"

export type Game = {
  id: string
  code?: string
  name: string
  icon_url?: string | null
}

export type ServiceSku = {
  id: string
  game_id: string
  name: string
  service_type: string
  duration_minutes: number
  price: number
}

export type Order = {
  id: string
  order_no: string
  user_id?: string
  game_id?: string
  sku_id?: string
  designated_player_id?: string | null
  status: OrderStatus
  quantity?: number
  unit_price?: number
  total_amount: number
  player_amount: number
  platform_fee: number
  version: number
}

export type Wallet = {
  id?: string
  availableBalance: number
  frozenBalance: number
  version?: number
}


export type PublicOffering = {
  id: string
  sku_id: string
  game_id: string
  game_name: string
  sku_name: string
  service_type: string
  duration_minutes: number
  price: number
  description: string
}

export type PublicReview = {
  id: string
  rating: number
  content: string
}

export type PublicPlayer = {
  id: string
  display_name: string
  avatar_url?: string | null
  bio: string
  gender?: string | null
  service_status: string
  rating: number
  review_count: number
  order_count: number
  offerings: PublicOffering[]
  reviews: PublicReview[]
}
