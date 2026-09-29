import { request } from "./client"
import { getDemoIdentities, type DemoIdentities } from "./demo"
import { ensureSession, usesWechatSession } from "./session"

type PlayerProfile = {
  id: string
  user_id: string
  display_name: string
}

export async function getRuntimeIdentities(): Promise<DemoIdentities> {
  if (!usesWechatSession()) {
    return getDemoIdentities()
  }

  const session = await ensureSession()
  const players: DemoIdentities["players"] = []

  if (session.roles.includes("PLAYER")) {
    const profile = await request<PlayerProfile>("/player/profile")
    players.push({
      userId: session.userId,
      playerId: profile.id,
      displayName: profile.display_name
    })
  }

  return {
    customer: {
      userId: session.userId,
      nickname: "微信用户"
    },
    players,
    admin: session.roles.includes("PLATFORM")
      ? {
          userId: session.userId,
          nickname: "平台用户"
        }
      : null
  }
}
