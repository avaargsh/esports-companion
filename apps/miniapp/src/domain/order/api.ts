import { request } from "../../api/client"
import type { Order } from "../../types/domain"
import type { ProductPrincipal } from "../../product/principal"

export function listCustomerOrders(
  principal: ProductPrincipal,
  limit = 50
): Promise<Order[]> {
  return request<Order[]>(`/orders?limit=${limit}`, {
    userId: principal.userId
  })
}
