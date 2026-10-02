export type OrderAction =
  | "CLAIM_ORDER"
  | "PAY"
  | "CANCEL"
  | "CONFIRM_FINISH"
  | "START_SERVICE"
  | "REQUEST_FINISH"
  | "REQUEST_REFUND"
  | "OPEN_DISPUTE"

export type CheckoutAction =
  | "CREATE_ORDER"
  | "CREATE_DESIGNATED_ORDER"

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
  available_actions?: CheckoutAction[]
}

export type ServicePlayer = {
  id: string
  display_name: string
  avatar_url?: string | null
  rating: number
  service_status: string
  binding: "ASSIGNED" | "DESIGNATED"
  assigned_by?: string | null
}

export type OrderMessage = {
  id: string
  order_id: string
  sender_user_id: string
  sender_role: "USER" | "PLAYER"
  message_type: "TEXT"
  content: string
  client_message_id: string
  created_at: string
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
  service_player?: ServicePlayer | null
  available_actions?: OrderAction[]
}

export type WalletAction = "REQUEST_WITHDRAWAL"

export type Wallet = {
  id?: string
  availableBalance: number
  frozenBalance: number
  version?: number
  availableActions?: WalletAction[]
}


export type PublicSkill = {
  id: string
  game_id: string
  game_name: string
  rank: string
  description: string
}

export type PlayerSkill = {
  id: string
  player_id: string
  game_id: string
  rank?: string | null
  description: string
  evidence_url?: string | null
  verification_status: "PENDING" | "APPROVED" | "REJECTED"
  review_note: string
  status: string
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
  skills: PublicSkill[]
  reviews: PublicReview[]
  available_actions?: CheckoutAction[]
}


export type OrderEvent = {
  id: string
  event_type: string
  from_status?: OrderStatus | null
  to_status?: OrderStatus | null
  actor_type: string
  created_at: string
}


export type Withdrawal = {
  id: string
  user_id: string
  wallet_id: string
  amount: number
  status: "PENDING" | "COMPLETED" | "REJECTED" | string
  provider: string
  provider_txn_id?: string | null
  failure_reason?: string | null
  created_at: string
  completed_at?: string | null
  rejected_at?: string | null
}
