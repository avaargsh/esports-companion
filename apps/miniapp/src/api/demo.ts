import { ensureSession } from "./auth"
import { request } from "./client"
import { isWeChatAuthMode } from "./config"

export type DemoIdentities = {
  customer: { userId: string; nickname: string }
  players: Array<{ userId: string; playerId: string; displayName: string }>
  admin: { userId: string; nickname: string } | null
}

let cached: DemoIdentities | null = null

export async function getDemoIdentities(): Promise<DemoIdentities> {
  if (isWeChatAuthMode()) {
    const session = await ensureSession()
    return {
      customer: {
        userId: session.userId,
        nickname: ""
      },
      players: session.roles.includes("PLAYER")
        ? [
            {
              userId: session.userId,
              playerId: "",
              displayName: ""
            }
          ]
        : [],
      admin: session.roles.includes("PLATFORM")
        ? {
            userId: session.userId,
            nickname: ""
          }
        : null
    }
  }

  if (!cached) {
    cached = await request<DemoIdentities>("/dev/demo-identities")
  }
  return cached
}
