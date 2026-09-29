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
