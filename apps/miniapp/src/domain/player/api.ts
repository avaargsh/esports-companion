import { request } from "../../api/client"
import type { Order, PlayerSkill } from "../../types/domain"

export type PlayerAction = "GO_AVAILABLE" | "GO_OFFLINE"

export type PlayerProfile = {
  id: string
  user_id: string
  display_name: string
  bio?: string
  verification_status: string
  service_status: string
  available_actions: PlayerAction[]
}

export type PlayerPoolOrder = Order

export type PlayerOffering = {
  id: string
  player_id: string
  sku_id: string
  price_override: number | null
  description: string
  status: string
}

export function getPlayerProfile(userId: string): Promise<PlayerProfile> {
  return request<PlayerProfile>("/player/profile", { userId })
}

export function applyPlayer(
  userId: string,
  displayName: string,
  bio: string
): Promise<PlayerProfile> {
  return request<PlayerProfile>("/player/apply", {
    method: "POST",
    userId,
    data: {
      display_name: displayName,
      bio
    }
  })
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

export function listPlayerOfferings(
  userId: string
): Promise<PlayerOffering[]> {
  return request<PlayerOffering[]>("/player/offerings", { userId })
}

export function updatePlayerOffering(
  userId: string,
  skuId: string,
  input: {
    priceOverride: number | null
    description: string
    status: string
  }
): Promise<PlayerOffering> {
  return request<PlayerOffering>(`/player/offerings/${skuId}`, {
    method: "PUT",
    userId,
    data: {
      price_override: input.priceOverride,
      description: input.description,
      status: input.status
    }
  })
}

export function listPlayerSkills(userId: string): Promise<PlayerSkill[]> {
  return request<PlayerSkill[]>("/player/skills", { userId })
}

export function upsertPlayerSkill(
  userId: string,
  gameId: string,
  input: {
    rank: string
    description: string
    evidenceUrl: string
  }
): Promise<PlayerSkill> {
  return request<PlayerSkill>(`/player/skills/${gameId}`, {
    method: "PUT",
    userId,
    data: {
      rank: input.rank,
      description: input.description,
      evidence_url: input.evidenceUrl
    }
  })
}
