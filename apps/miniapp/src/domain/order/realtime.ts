import { connectOrderRealtime, type RealtimeSocketTask } from "../../api/realtime"

export type OrderRealtimeHandlers = {
  onConnectionChange?: (connected: boolean) => void
  onStatusChanged?: () => void
  onMessageCreated?: () => void
  onReconnected?: () => void
}

export type OrderRealtimeSubscription = {
  close: () => void
}

type OrderRealtimePayload = {
  type?: string
  eventId?: string
}

const DEDUPE_WINDOW = 128
const RECONNECT_BASE_MS = 750
const RECONNECT_MAX_MS = 8_000

export async function subscribeOrderRealtime({
  orderId,
  userId,
  handlers
}: {
  orderId: string
  userId: string
  handlers: OrderRealtimeHandlers
}): Promise<OrderRealtimeSubscription> {
  if (!orderId) throw new Error("ORDER_ID_REQUIRED")
  if (!userId) throw new Error("ORDER_USER_REQUIRED")

  const seen = new Set<string>()
  const seenOrder: string[] = []
  let socket: RealtimeSocketTask | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectAttempt = 0
  let connecting = false
  let closed = false
  let openedOnce = false

  function remember(eventId?: string): boolean {
    if (!eventId) return true
    if (seen.has(eventId)) return false

    seen.add(eventId)
    seenOrder.push(eventId)
    if (seenOrder.length > DEDUPE_WINDOW) {
      const oldest = seenOrder.shift()
      if (oldest) seen.delete(oldest)
    }
    return true
  }

  function clearReconnectTimer() {
    if (!reconnectTimer) return
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }

  function scheduleReconnect() {
    if (closed || reconnectTimer || connecting) return

    handlers.onConnectionChange?.(false)
    const exponent = Math.min(reconnectAttempt, 4)
    const delay = Math.min(
      RECONNECT_MAX_MS,
      RECONNECT_BASE_MS * 2 ** exponent
    )
    reconnectAttempt += 1

    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      void connect()
    }, delay)
  }

  async function connect() {
    if (closed || connecting) return
    connecting = true

    let task: RealtimeSocketTask
    try {
      task = await connectOrderRealtime({
        orderId,
        demoUserId: userId
      })
    } catch {
      connecting = false
      scheduleReconnect()
      return
    }
    connecting = false

    if (closed) {
      task.close({})
      return
    }

    socket = task

    task.onOpen(() => {
      if (closed || socket !== task) {
        task.close({})
        return
      }

      const shouldHeal = openedOnce || reconnectAttempt > 0
      openedOnce = true
      reconnectAttempt = 0
      clearReconnectTimer()
      handlers.onConnectionChange?.(true)

      task.send({
        data: JSON.stringify({
          type: "subscribe",
          channels: [`order:${orderId}`]
        })
      })

      if (shouldHeal) {
        handlers.onReconnected?.()
      }
    })

    task.onClose(() => {
      if (socket !== task) return
      socket = null
      handlers.onConnectionChange?.(false)
      scheduleReconnect()
    })

    task.onError(() => {
      if (socket !== task) return
      socket = null
      handlers.onConnectionChange?.(false)
      task.close({})
      scheduleReconnect()
    })

    task.onMessage(message => {
      if (closed || socket !== task) return
      try {
        const payload = JSON.parse(
          String(message.data)
        ) as OrderRealtimePayload
        if (!remember(payload.eventId)) return

        if (payload.type === "order.status_changed") {
          handlers.onStatusChanged?.()
        }
        if (payload.type === "order.message_created") {
          handlers.onMessageCreated?.()
        }
      } catch {
        // Ignore unsupported realtime messages.
      }
    })
  }

  void connect()

  return {
    close() {
      closed = true
      clearReconnectTimer()
      handlers.onConnectionChange?.(false)
      const current = socket
      socket = null
      current?.close({})
    }
  }
}
