import { request } from "../../api/client"
import type { Game } from "../../types/domain"

export function listGames(): Promise<Game[]> {
  return request<Game[]>("/games")
}
