import { request } from "./client"

export type DemoIdentities = {
  customer: { userId: string; nickname: string }
  players: Array<{ userId: string; playerId: string; displayName: string }>
  admin: { userId: string; nickname: string } | null
}

let cached: DemoIdentities | null = null

export async function getDemoIdentities(): Promise<DemoIdentities> {
  if (!cached) {
    cached = await request<DemoIdentities>("/dev/demo-identities")
  }
  return cached
}
