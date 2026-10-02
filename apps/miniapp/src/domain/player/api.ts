import { request } from "../../api/client"
import type { Order } from "../../types/domain"
import type { ProductPrincipal } from "../../product/principal"

export type PlayerProfile = {
  id: string
  user_id: string
  display_name: string
  verification_status: string
  service_status: string
}

export function getPlayerProfile(
  principal: ProductPrincipal
): Promise<PlayerProfile> {
  return request<PlayerProfile>("/player/profile", {
    userId: principal.userId
  })
}

export function listPlayerOrders(
  principal: ProductPrincipal
): Promise<Order[]> {
  return request<Order[]>("/player/orders", {
    userId: principal.userId
  })
}

export function updatePlayerServiceStatus(
  principal: ProductPrincipal,
  serviceStatus: "AVAILABLE" | "OFFLINE"
): Promise<PlayerProfile> {
  return request<PlayerProfile>("/player/profile", {
    method: "PUT",
    userId: principal.userId,
    data: { service_status: serviceStatus }
  })
}
