import { request } from "../../api/client"
import type { Wallet } from "../../types/domain"
import type { ProductPrincipal } from "../../product/principal"

export function getWallet(
  principal: ProductPrincipal
): Promise<Wallet> {
  return request<Wallet>("/wallet", {
    userId: principal.userId
  })
}
