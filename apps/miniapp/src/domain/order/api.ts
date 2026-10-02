import { request } from "../../api/client"
import type { Order } from "../../types/domain"

export function listCustomerOrders(
  userId: string,
  limit = 50
): Promise<Order[]> {
  return request<Order[]>(`/orders?limit=${limit}`, {
    userId
  })
}
