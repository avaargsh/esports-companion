import { connectOrderRealtime } from "../../api/realtime"

export type OrderRealtimeHandlers = {
  onConnectionChange?: (connected: boolean) => void
  onStatusChanged?: () => void
  onMessageCreated?: () => void
}

export type OrderRealtimeSubscription = {
  close: () => void
}

type OrderRealtimePayload = {
  type?: string
  eventId?: string
}

const DEDUPE_WINDOW = 128

export async function subscribeOrderRealtime({
  orderId,
  userId,
  handlers
}: {
  orderId: string
  userId: string
  handlers: OrderRealtimeHandlers
}): Promise<OrderRealtimeSubscription> {
  const task = await connectOrderRealtime({
    orderId,
    demoUserId: userId
  })

  const seen = new Set<string>()
  const seenOrder: string[] = []

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

  task.onOpen(() => {
    handlers.onConnectionChange?.(true)
    task.send({
      data: JSON.stringify({
        type: "subscribe",
        channels: [`order:${orderId}`]
      })
    })
  })

  task.onClose(() => {
    handlers.onConnectionChange?.(false)
  })

  task.onError(() => {
    handlers.onConnectionChange?.(false)
  })

  task.onMessage(message => {
    try {
      const payload = JSON.parse(String(message.data)) as OrderRealtimePayload
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

  return {
    close() {
      handlers.onConnectionChange?.(false)
      task.close({})
    }
  }
}
