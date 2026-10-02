import { request } from "../../api/client"
import type { Order } from "../../types/domain"

export type PlayerProfile = {
  id: string
  user_id: string
  display_name: string
  verification_status: string
  service_status: string
}

export function getPlayerProfile(userId: string): Promise<PlayerProfile> {
  return request<PlayerProfile>("/player/profile", { userId })
}

export function listPlayerOrders(userId: string): Promise<Order[]> {
  return request<Order[]>("/player/orders", { userId })
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
