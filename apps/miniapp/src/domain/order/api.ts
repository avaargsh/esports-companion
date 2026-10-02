import { request } from "../../api/client"
import type { Order, OrderEvent } from "../../types/domain"

export type OrderAftercareKind = "refund" | "dispute"

export function listCustomerOrders(
  userId: string,
  limit = 50
): Promise<Order[]> {
  return request<Order[]>(`/orders?limit=${limit}`, {
    userId
  })
}

export function listPlayerOrders(userId: string): Promise<Order[]> {
  return request<Order[]>("/player/orders", { userId })
}

export function listPlayerOrderPool(
  userId: string,
  gameId: string,
  limit = 20
): Promise<Order[]> {
  return request<Order[]>(
    `/player/order-pool?game_id=${encodeURIComponent(gameId)}&limit=${limit}`,
    { userId }
  )
}

export function claimPlayerOrder(
  userId: string,
  orderId: string,
  expectedVersion: number
): Promise<Order> {
  return request<Order>(`/player/orders/${orderId}/claim`, {
    method: "POST",
    userId,
    data: { expected_version: expectedVersion }
  })
}

export function getOrderDetail(
  userId: string,
  orderId: string
): Promise<Order> {
  return request<Order>(`/orders/${orderId}`, { userId })
}

export function listOrderEvents(
  userId: string,
  orderId: string
): Promise<OrderEvent[]> {
  return request<OrderEvent[]>(`/orders/${orderId}/events`, { userId })
}

export function startPlayerOrder(
  userId: string,
  orderId: string
): Promise<Order> {
  return request<Order>(`/player/orders/${orderId}/start`, {
    method: "POST",
    userId
  })
}

export function finishPlayerOrder(
  userId: string,
  orderId: string
): Promise<Order> {
  return request<Order>(`/player/orders/${orderId}/finish`, {
    method: "POST",
    userId
  })
}

export function confirmCustomerOrder(
  userId: string,
  orderId: string
): Promise<Order> {
  return request<Order>(`/orders/${orderId}/confirm`, {
    method: "POST",
    userId
  })
}

export function cancelCustomerOrder(
  userId: string,
  orderId: string
): Promise<Order> {
  return request<Order>(`/orders/${orderId}/cancel`, {
    method: "POST",
    userId
  })
}

export function createOrderAftercare(
  userId: string,
  orderId: string,
  kind: OrderAftercareKind,
  description: string
): Promise<unknown> {
  return request(`/orders/${orderId}/disputes`, {
    method: "POST",
    userId,
    headers: { "Idempotency-Key": `miniapp-${kind}-${orderId}-${userId}` },
    data: {
      reason_code:
        kind === "refund" ? "CANCEL_BEFORE_SERVICE" : "SERVICE_ISSUE",
      description
    }
  })
}

export function submitOrderReview(
  userId: string,
  orderId: string,
  rating: number,
  content: string
): Promise<unknown> {
  return request(`/orders/${orderId}/reviews`, {
    method: "POST",
    userId,
    data: { rating, content }
  })
}
