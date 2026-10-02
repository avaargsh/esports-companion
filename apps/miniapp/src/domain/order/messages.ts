import { request } from "../../api/client"
import type { OrderMessage } from "../../types/domain"

export function listOrderMessages(
  userId: string,
  orderId: string,
  limit = 100
): Promise<OrderMessage[]> {
  return request<OrderMessage[]>(
    `/orders/${orderId}/messages?limit=${limit}`,
    { userId }
  )
}

export function sendOrderMessage(
  userId: string,
  orderId: string,
  content: string,
  clientMessageId: string
): Promise<OrderMessage> {
  return request<OrderMessage>(`/orders/${orderId}/messages`, {
    method: "POST",
    userId,
    data: {
      client_message_id: clientMessageId,
      content
    }
  })
}

export function orderMessageError(message: string): string {
  if (message.includes("ORDER_MESSAGE_READ_ONLY")) {
    return "订单已结束，当前会话仅可查看"
  }
  if (message.includes("FORBIDDEN") || message.includes("NOT_PARTICIPANT")) {
    return "当前账号无法查看这笔订单的沟通记录"
  }
  if (message.includes("NETWORK") || message.includes("timeout")) {
    return "网络不稳定，请稍后重试"
  }
  return "消息暂时不可用，请稍后重试"
}
