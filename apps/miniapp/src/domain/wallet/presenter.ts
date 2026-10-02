import type { Withdrawal } from "../../types/domain"

export function withdrawalStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    PENDING: "审核 / 打款中",
    COMPLETED: "已到账",
    REJECTED: "已退回"
  }
  return labels[status] || status
}

export function formatWithdrawalTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  return date.toLocaleString()
}

export function pendingWithdrawalAmount(items: Withdrawal[]): number {
  return items
    .filter(item => item.status === "PENDING")
    .reduce((sum, item) => sum + item.amount, 0)
}
