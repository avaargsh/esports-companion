import type { OrderStatus } from "../types/domain"

export type OrderStatusMeta = {
  label: string
  description: string
  tone: "neutral" | "primary" | "success" | "warning" | "danger"
  progress: number
}

const STATUS: Record<OrderStatus, OrderStatusMeta> = {
  WAITING_PAYMENT: { label: "待支付", description: "完成支付后开始匹配陪玩", tone: "warning", progress: 8 },
  PAID: { label: "已支付", description: "支付成功，正在进入匹配", tone: "primary", progress: 22 },
  MATCHING: { label: "匹配中", description: "订单已进入抢单大厅", tone: "primary", progress: 36 },
  ACCEPTED: { label: "已接单", description: "陪玩已接单，等待开始服务", tone: "primary", progress: 54 },
  IN_SERVICE: { label: "服务中", description: "本次陪玩服务正在进行", tone: "success", progress: 72 },
  FINISH_REQUESTED: { label: "待确认完成", description: "陪玩已申请结束，请确认服务结果", tone: "warning", progress: 88 },
  COMPLETED: { label: "已完成", description: "服务已完成，正在结算", tone: "success", progress: 96 },
  SETTLED: { label: "已结算", description: "订单已完成结算", tone: "success", progress: 100 },
  CANCELLED: { label: "已取消", description: "订单已取消", tone: "neutral", progress: 0 },
  REFUNDING: { label: "退款中", description: "退款正在处理中", tone: "warning", progress: 0 },
  REFUNDED: { label: "已退款", description: "退款已完成", tone: "neutral", progress: 0 },
  DISPUTED: { label: "争议处理中", description: "平台正在处理本次订单争议", tone: "danger", progress: 0 }
}

export function orderStatusMeta(status: OrderStatus): OrderStatusMeta {
  return STATUS[status]
}

export function isActiveOrder(status: OrderStatus): boolean {
  return [
    "WAITING_PAYMENT",
    "PAID",
    "MATCHING",
    "ACCEPTED",
    "IN_SERVICE",
    "FINISH_REQUESTED"
  ].includes(status)
}
