import { request } from "../../api/client"
import type { PublicPlayer } from "../../types/domain"

export function listPublicPlayers({
  gameId,
  limit = 30
}: {
  gameId?: string
  limit?: number
} = {}): Promise<PublicPlayer[]> {
  const query = [`limit=${limit}`]
  if (gameId) {
    query.push(`game_id=${encodeURIComponent(gameId)}`)
  }
  return request<PublicPlayer[]>(`/players?${query.join("&")}`)
}

export function getPublicPlayer(
  playerId: string
): Promise<PublicPlayer> {
  return request<PublicPlayer>(
    `/players/${encodeURIComponent(playerId)}`
  )
}
