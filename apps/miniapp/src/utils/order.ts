import type { OrderStatus } from "../types/domain"

export type OrderRole = "CUSTOMER" | "PLAYER"
export type StatusTone = "neutral" | "primary" | "success" | "warning" | "danger"

export type OrderStatusMeta = {
  label: string
  description: string
  tone: StatusTone
  progress: number
  step: number
}

const ORDER_STATUS_BY_TEXT: Record<string, OrderStatus> = {
  "待支付": "WAITING_PAYMENT",
  "已支付": "PAID",
  "支付成功": "PAID",
  "待接单": "MATCHING",
  "等待接单": "MATCHING",
  "已接单": "ACCEPTED",
  "已接单，准备开始": "ACCEPTED",
  "服务中": "IN_SERVICE",
  "服务进行中": "IN_SERVICE",
  "待确认完成": "FINISH_REQUESTED",
  "请确认完成": "FINISH_REQUESTED",
  "已完成": "COMPLETED",
  "已结算": "SETTLED",
  "已结算入账": "SETTLED",
  "已取消": "CANCELLED",
  "退款处理中": "REFUNDING",
  "已退款": "REFUNDED",
  "订单已退款": "REFUNDED",
  "争议处理中": "DISPUTED",
  "售后处理中": "DISPUTED"
}

export function orderStatusCode(status?: string | null): OrderStatus {
  if (!status) return "WAITING_PAYMENT"
  return (ORDER_STATUS_BY_TEXT[status] || status) as OrderStatus
}

const CUSTOMER_STATUS: Record<OrderStatus, OrderStatusMeta> = {
  WAITING_PAYMENT: {
    label: "待支付",
    description: "完成支付后开始匹配陪玩",
    tone: "neutral",
    progress: 10,
    step: 1
  },
  PAID: {
    label: "支付成功",
    description: "支付已确认，正在进入接单队列",
    tone: "primary",
    progress: 26,
    step: 2
  },
  MATCHING: {
    label: "等待接单",
    description: "订单已进入抢单大厅，请稍候",
    tone: "primary",
    progress: 36,
    step: 2
  },
  ACCEPTED: {
    label: "已接单，准备开始",
    description: "陪玩已接单，等待开始服务",
    tone: "primary",
    progress: 55,
    step: 3
  },
  IN_SERVICE: {
    label: "服务进行中",
    description: "本次陪玩服务正在进行",
    tone: "warning",
    progress: 74,
    step: 4
  },
  FINISH_REQUESTED: {
    label: "请确认完成",
    description: "陪玩已申请结束，请确认本次服务结果",
    tone: "warning",
    progress: 88,
    step: 4
  },
  COMPLETED: {
    label: "已完成",
    description: "服务已完成，平台正在结算",
    tone: "success",
    progress: 96,
    step: 5
  },
  SETTLED: {
    label: "已完成",
    description: "订单已完成，可评价本次服务",
    tone: "success",
    progress: 100,
    step: 5
  },
  CANCELLED: {
    label: "已取消",
    description: "本次订单已取消",
    tone: "neutral",
    progress: 0,
    step: 1
  },
  REFUNDING: {
    label: "退款处理中",
    description: "平台正在处理退款，完成后订单会自动更新",
    tone: "warning",
    progress: 88,
    step: 4
  },
  REFUNDED: {
    label: "已退款",
    description: "退款已完成，资金将按支付渠道原路退回",
    tone: "success",
    progress: 100,
    step: 5
  },
  DISPUTED: {
    label: "售后处理中",
    description: "平台正在处理本次订单争议",
    tone: "danger",
    progress: 74,
    step: 4
  }
}

const PLAYER_STATUS: Record<OrderStatus, OrderStatusMeta> = {
  WAITING_PAYMENT: {
    label: "用户待支付",
    description: "订单尚未进入可接单状态",
    tone: "neutral",
    progress: 10,
    step: 1
  },
  PAID: {
    label: "等待进入大厅",
    description: "订单已支付，正在进入抢单队列",
    tone: "primary",
    progress: 26,
    step: 2
  },
  MATCHING: {
    label: "待抢单",
    description: "订单正在抢单大厅等待陪玩接单",
    tone: "primary",
    progress: 36,
    step: 2
  },
  ACCEPTED: {
    label: "待开始",
    description: "你已接单，请及时开始服务",
    tone: "primary",
    progress: 55,
    step: 3
  },
  IN_SERVICE: {
    label: "服务中",
    description: "本次陪玩服务正在进行",
    tone: "warning",
    progress: 74,
    step: 4
  },
  FINISH_REQUESTED: {
    label: "等待用户确认",
    description: "已申请结束，等待用户确认完成",
    tone: "warning",
    progress: 88,
    step: 4
  },
  COMPLETED: {
    label: "已完成",
    description: "用户已确认完成，正在结算",
    tone: "success",
    progress: 96,
    step: 5
  },
  SETTLED: {
    label: "已结算入账",
    description: "本单收入已完成结算",
    tone: "success",
    progress: 100,
    step: 5
  },
  CANCELLED: {
    label: "已取消",
    description: "本次订单已取消",
    tone: "neutral",
    progress: 0,
    step: 1
  },
  REFUNDING: {
    label: "退款处理中",
    description: "平台正在处理退款，完成后订单会自动更新",
    tone: "warning",
    progress: 88,
    step: 4
  },
  REFUNDED: {
    label: "订单已退款",
    description: "本次订单退款已完成",
    tone: "success",
    progress: 100,
    step: 5
  },
  DISPUTED: {
    label: "售后处理中",
    description: "平台正在处理本次订单争议",
    tone: "danger",
    progress: 74,
    step: 4
  }
}

export function orderStatusMeta(
  status: OrderStatus | string,
  role: OrderRole = "CUSTOMER"
): OrderStatusMeta {
  const code = orderStatusCode(status)
  return role === "PLAYER" ? PLAYER_STATUS[code] : CUSTOMER_STATUS[code]
}

export function isActiveOrder(status: OrderStatus | string): boolean {
  return [
    "WAITING_PAYMENT",
    "PAID",
    "MATCHING",
    "ACCEPTED",
    "IN_SERVICE",
    "FINISH_REQUESTED"
  ].includes(orderStatusCode(status))
}

export function isCustomerCancellable(status: OrderStatus | string): boolean {
  return ["WAITING_PAYMENT", "MATCHING"].includes(orderStatusCode(status))
}

export function claimErrorMessage(message: string): string {
  if (
    message.includes("ORDER_ALREADY_CLAIMED") ||
    message.includes("already claimed") ||
    message.includes("version")
  ) {
    return "手慢了，这单已经被别人抢走"
  }
  if (
    message.includes("PLAYER_NOT_ELIGIBLE") ||
    message.includes("PLAYER_NOT_APPROVED")
  ) {
    return "当前陪玩状态或技能不满足接单条件"
  }
  if (message.includes("PLAYER_PROFILE_NOT_FOUND")) {
    return "未找到陪玩身份，请先完成陪玩资料"
  }
  return message || "操作失败，请稍后重试"
}

export function playerActionErrorMessage(message: string): string {
  if (
    message.includes("ASSIGNMENT") ||
    message.includes("NOT_ASSIGNED")
  ) {
    return "这笔订单已不属于当前履约任务，请返回服务单刷新"
  }
  if (
    message.includes("not allowed") ||
    message.includes("INVALID") ||
    message.includes("status")
  ) {
    return "订单状态已经变化，请刷新后再操作"
  }
  return claimErrorMessage(message)
}
