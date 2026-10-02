import { request } from "../../api/client"
import type { Wallet } from "../../types/domain"

export function getWallet(userId: string): Promise<Wallet> {
  return request<Wallet>("/wallet", { userId })
}
