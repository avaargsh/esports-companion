import type { Order, OrderEvent, OrderStatus } from "../../types/domain"
import { orderStatusMeta } from "../../utils/order"

export type CustomerPrimaryAction =
  | { kind: "pay"; label: string }
  | { kind: "confirm"; label: string }
  | { kind: "again"; label: string }

export type CustomerSecondaryAction = {
  kind: "cancel"
  label: string
}

export type DemoJourney = {
  step: number
  title: string
  description: string
}

const CUSTOMER_EVENT_LABELS: Record<string, string> = {
  ORDER_CREATED: "订单已创建",
  PAYMENT_SUCCESS: "支付成功",
  ORDER_ENTERED_MATCHING: "进入接单队列",
  ORDER_CLAIMED: "陪玩已接单",
  ORDER_ASSIGNED: "陪玩已接单",
  SERVICE_STARTED: "服务已开始",
  FINISH_REQUESTED: "陪玩申请完成",
  USER_CONFIRMED_FINISH: "用户确认完成",
  AUTO_CONFIRMED_FINISH: "超时自动确认",
  ORDER_SETTLED: "订单已结算",
  ORDER_CANCELLED: "订单已取消",
  DISPUTE_OPENED: "已申请平台介入",
  REFUND_REQUESTED: "退款申请处理中",
  REFUND_COMPLETED: "退款已完成"
}

const CUSTOMER_ACTOR_LABELS: Record<string, string> = {
  USER: "你",
  PLAYER: "陪玩",
  SYSTEM: "系统",
  PAYMENT: "支付系统",
  PLATFORM: "平台"
}

const CHAT_VISIBLE_STATUSES: OrderStatus[] = [
  "ACCEPTED",
  "IN_SERVICE",
  "FINISH_REQUESTED",
  "COMPLETED",
  "SETTLED",
  "DISPUTED",
  "REFUNDING",
  "REFUNDED"
]

const CHAT_WRITABLE_STATUSES: OrderStatus[] = [
  "ACCEPTED",
  "IN_SERVICE",
  "FINISH_REQUESTED",
  "DISPUTED"
]

function hasAction(order: Order, action: NonNullable<Order["available_actions"]>[number]) {
  return order.available_actions?.includes(action) ?? false
}

export function customerPrimaryAction(
  order: Order | null
): CustomerPrimaryAction | null {
  if (!order) return null
  if (hasAction(order, "PAY")) {
    return { kind: "pay", label: "去支付" }
  }
  if (hasAction(order, "CONFIRM_FINISH")) {
    return { kind: "confirm", label: "确认完成" }
  }
  if (["CANCELLED", "REFUNDED"].includes(order.status)) {
    return { kind: "again", label: "再来一单" }
  }
  return null
}

export function customerSecondaryAction(
  order: Order | null
): CustomerSecondaryAction | null {
  if (!order || !hasAction(order, "CANCEL")) return null
  return { kind: "cancel", label: "取消订单" }
}

export function isOrderChatVisible(status?: OrderStatus): boolean {
  return Boolean(status && CHAT_VISIBLE_STATUSES.includes(status))
}

export function isOrderChatWritable(status?: OrderStatus): boolean {
  return Boolean(status && CHAT_WRITABLE_STATUSES.includes(status))
}

export function customerDemoJourney(
  status: OrderStatus | undefined,
  reviewed: boolean
): DemoJourney | null {
  if (status === "WAITING_PAYMENT") {
    return {
      step: 2,
      title: "完成模拟支付",
      description: "支付后订单会进入公开匹配池；下一步到「我的」切换陪玩身份。"
    }
  }
  if (status === "MATCHING") {
    return {
      step: 3,
      title: "切到陪玩端抢单",
      description: "底部进入「我的」→「陪玩工作台」→「抢单大厅」，接走这笔订单。"
    }
  }
  if (status === "ACCEPTED" || status === "IN_SERVICE") {
    return {
      step: 4,
      title: "等待陪玩履约",
      description: "陪玩端会开始并完成服务；订单内聊天和状态会持续留痕。"
    }
  }
  if (status === "FINISH_REQUESTED") {
    return {
      step: 5,
      title: "确认本次服务完成",
      description: "确认后平台执行结算，陪玩收入才会进入可用余额。"
    }
  }
  if (status === "SETTLED" && !reviewed) {
    return {
      step: 6,
      title: "最后一步：提交评价",
      description: "评价会进入陪玩公开主页，形成下一次用户选择所依赖的信誉。"
    }
  }
  if (status === "SETTLED" && reviewed) {
    return {
      step: 6,
      title: "陪玩交易闭环完成",
      description: "成交、履约、结算和评价均已完成；可点「服务大神」查看信誉回流。"
    }
  }
  return null
}

export function customerEventTitle(event: OrderEvent): string {
  if (CUSTOMER_EVENT_LABELS[event.event_type]) {
    return CUSTOMER_EVENT_LABELS[event.event_type]
  }
  if (event.to_status) {
    return orderStatusMeta(event.to_status, "CUSTOMER").label
  }
  return event.event_type.replaceAll("_", " ")
}

export function customerActorLabel(actor: string): string {
  return CUSTOMER_ACTOR_LABELS[actor] || "系统"
}

export function formatOrderTimestamp(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
