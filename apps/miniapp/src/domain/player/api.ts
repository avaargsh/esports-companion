import { request } from "../../api/client"
import type { Order } from "../../types/domain"

export type PlayerAction = "GO_AVAILABLE" | "GO_OFFLINE"

export type PlayerProfile = {
  id: string
  user_id: string
  display_name: string
  verification_status: string
  service_status: string
  available_actions: PlayerAction[]
}

export type PlayerPoolOrder = Order

export function getPlayerProfile(userId: string): Promise<PlayerProfile> {
  return request<PlayerProfile>("/player/profile", { userId })
}

export function listPlayerOrders(userId: string): Promise<Order[]> {
  return request<Order[]>("/player/orders", { userId })
}

export function listPlayerOrderPool(
  userId: string,
  gameId: string,
  limit = 20
): Promise<PlayerPoolOrder[]> {
  return request<PlayerPoolOrder[]>(
    `/player/order-pool?game_id=${encodeURIComponent(gameId)}&limit=${limit}`,
    { userId }
  )
}

export function claimPlayerOrder(
  userId: string,
  orderId: string,
  expectedVersion: number
): Promise<Order> {
  return request<Order>(`/player/orders/${orderId}/claim`, {
    method: "POST",
    userId,
    data: { expected_version: expectedVersion }
  })
}

export function updatePlayerServiceStatus(
  userId: string,
  serviceStatus: "AVAILABLE" | "OFFLINE"
): Promise<PlayerProfile> {
  return request<PlayerProfile>("/player/profile", {
    method: "PUT",
    userId,
    data: { service_status: serviceStatus }
  })
}
