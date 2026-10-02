import { request } from "../../api/client"
import type { Game, ServiceSku } from "../../types/domain"

export function listGames(): Promise<Game[]> {
  return request<Game[]>("/games")
}

export function listGameSkus(gameId: string): Promise<ServiceSku[]> {
  return request<ServiceSku[]>(
    `/games/${encodeURIComponent(gameId)}/skus`
  )
}
