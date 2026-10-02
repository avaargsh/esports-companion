import { request } from "../../api/client"
import type { Wallet, Withdrawal } from "../../types/domain"

export function getWallet(userId: string): Promise<Wallet> {
  return request<Wallet>("/wallet", { userId })
}

export function listWithdrawals(userId: string): Promise<Withdrawal[]> {
  return request<Withdrawal[]>("/withdrawals", { userId })
}

export function createWithdrawal(
  userId: string,
  amount: number,
  idempotencyKey: string
): Promise<Withdrawal> {
  return request<Withdrawal>("/withdrawals", {
    method: "POST",
    userId,
    headers: { "Idempotency-Key": idempotencyKey },
    data: { amount }
  })
}
