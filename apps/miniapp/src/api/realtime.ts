import { ensureSession } from "./auth"
import { API_ORIGIN, isWeChatAuthMode } from "./config"

export type RealtimeSocketTask = {
  onOpen: (callback: () => void) => void
  onClose: (callback: () => void) => void
  onError: (callback: () => void) => void
  onMessage: (callback: (message: { data: unknown }) => void) => void
  send: (options: { data: string }) => void
  close: (options?: Record<string, unknown>) => void
}

type UniSocketGlobal = typeof uni & {
  onSocketOpen?: (callback: () => void) => void
  onSocketClose?: (callback: () => void) => void
  onSocketError?: (callback: () => void) => void
  onSocketMessage?: (callback: (message: { data: unknown }) => void) => void
  sendSocketMessage?: (options: { data: string }) => void
  closeSocket?: (options?: Record<string, unknown>) => void
}

function normalizeSocketTask(rawTask: unknown): RealtimeSocketTask {
  const task = rawTask as Partial<RealtimeSocketTask>
  const socketGlobal = uni as UniSocketGlobal

  return {
    onOpen(callback) {
      if (typeof task.onOpen === "function") {
        task.onOpen(callback)
        return
      }
      socketGlobal.onSocketOpen?.(callback)
    },
    onClose(callback) {
      if (typeof task.onClose === "function") {
        task.onClose(callback)
        return
      }
      socketGlobal.onSocketClose?.(callback)
    },
    onError(callback) {
      if (typeof task.onError === "function") {
        task.onError(callback)
        return
      }
      socketGlobal.onSocketError?.(callback)
    },
    onMessage(callback) {
      if (typeof task.onMessage === "function") {
        task.onMessage(callback)
        return
      }
      socketGlobal.onSocketMessage?.(callback)
    },
    send(options) {
      if (typeof task.send === "function") {
        task.send(options)
        return
      }
      socketGlobal.sendSocketMessage?.(options)
    },
    close(options = {}) {
      if (typeof task.close === "function") {
        task.close(options)
        return
      }
      socketGlobal.closeSocket?.(options)
    }
  }
}

export async function connectOrderRealtime({
  orderId,
  demoUserId
}: {
  orderId: string
  demoUserId: string
}): Promise<RealtimeSocketTask> {
  if (!orderId) throw new Error("ORDER_ID_REQUIRED")
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

  const rawTask = uni.connectSocket({
    url,
    header
  })

  return normalizeSocketTask(rawTask)
}
