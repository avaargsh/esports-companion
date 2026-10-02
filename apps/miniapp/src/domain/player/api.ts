import { request } from "../../api/client"

export type PlayerProfile = {
  id: string
  user_id: string
  display_name: string
  bio?: string
  verification_status: string
  service_status: string
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
