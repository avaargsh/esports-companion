import { ensureSession } from "./auth"
import { request } from "./client"
import { isWeChatAuthMode } from "./config"

export type DemoIdentities = {
  customer: { userId: string; nickname: string }
  players: Array<{ userId: string; playerId: string; displayName: string }>
  admin: { userId: string; nickname: string } | null
}

type MeResponse = {
  userId: string
  roles: string[]
  status: string
}

type PlayerIdentity = {
  id: string
  user_id: string
  display_name: string
}

let cached: DemoIdentities | null = null

export async function getDemoIdentities(): Promise<DemoIdentities> {
  if (isWeChatAuthMode()) {
    const session = await ensureSession()
    const me = await request<MeResponse>("/auth/me", {
      userId: session.userId
    })

    let players: DemoIdentities["players"] = []
    if (me.roles.includes("PLAYER")) {
      const profile = await request<PlayerIdentity>("/player/profile", {
        userId: session.userId
      })
      players = [
        {
          userId: session.userId,
          playerId: profile.id,
          displayName: profile.display_name
        }
      ]
    }

    return {
      customer: {
        userId: session.userId,
        nickname: "微信用户"
      },
      players,
      admin: me.roles.includes("PLATFORM")
        ? {
            userId: session.userId,
            nickname: "平台运营"
          }
        : null
    }
  }

  if (!cached) {
    cached = await request<DemoIdentities>("/dev/demo-identities")
  }
  return cached
}
