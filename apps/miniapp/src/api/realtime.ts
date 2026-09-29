import { ensureSession } from "./auth"
import { API_ORIGIN, isWeChatAuthMode } from "./config"

export async function connectOrderRealtime(
  *,
  orderId,
  demoUserId
}: {
  orderId: string
  demoUserId: string
}): Promise<UniApp.SocketTask> {
  const baseUrl = API_ORIGIN.replace(/^http/, "ws") + "/ws"

  let url = baseUrl
  let header: Record<string, string> | undefined

  if (isWeChatAuthMode()) {
    const session = await ensureSession()
    header = {
      Authorization: `${session.tokenType || "Bearer"} ${session.accessToken}`
    }
  } else {
    url += `?user_id=${encodeURIComponent(demoUserId)}`
  }

  return uni.connectSocket({
    url,
    header
  }) as unknown as UniApp.SocketTask
}
