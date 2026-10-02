import { request } from "../../api/client"
import type { PublicPlayer } from "../../types/domain"

export function listPublicPlayers({
  gameId,
  limit = 30
}: {
  gameId?: string
  limit?: number
} = {}): Promise<PublicPlayer[]> {
  const params = new URLSearchParams()
  params.set("limit", String(limit))
  if (gameId) params.set("game_id", gameId)
  return request<PublicPlayer[]>(`/players?${params.toString()}`)
}

export function getPublicPlayer(
  playerId: string
): Promise<PublicPlayer> {
  return request<PublicPlayer>(
    `/players/${encodeURIComponent(playerId)}`
  )
}
