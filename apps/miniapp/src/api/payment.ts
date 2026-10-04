import { request } from "./client"
import { isWeChatAuthMode } from "./config"
import {
  requestWeChatPayment,
  type WeChatPaymentPayload
} from "../platform/wechat"
import type { Order } from "../types/domain"

type WeChatClientPayload = WeChatPaymentPayload

type PaymentPreparation = {
  order_id: string
  order_status: string
  order_status_code?: string
  provider: string
  payment_status: string
  payment_status_code?: string
  client_payload: Record<string, unknown>
  replayed: boolean
}

export type PaymentStartResult =
  | { mode: "mock"; order: Order }
  | { mode: "wechat"; alreadyConfirmed: boolean }

function asWeChatPayload(value: Record<string, unknown>): WeChatClientPayload {
  const payload = value as Partial<WeChatClientPayload>
  for (const field of ["timeStamp", "nonceStr", "package", "signType", "paySign"] as const) {
    if (typeof payload[field] !== "string" || !payload[field]) {
      throw new Error("WECHAT_PAYMENT_CLIENT_PAYLOAD_INVALID")
    }
  }
  return payload as WeChatClientPayload
}

export async function startOrderPayment(
  orderId: string,
  userId: string
): Promise<PaymentStartResult> {
  const idempotencyKey = `miniapp-payment-${orderId}`

  if (!isWeChatAuthMode()) {
    const order = await request<Order>(`/orders/${orderId}/mock-pay`, {
      method: "POST",
      userId,
      headers: { "Idempotency-Key": idempotencyKey }
    })
    return { mode: "mock", order }
  }

  const preparation = await request<PaymentPreparation>(
    `/orders/${orderId}/payments`,
    {
      method: "POST",
      userId,
      headers: { "Idempotency-Key": idempotencyKey }
    }
  )

  const paymentStatus = preparation.payment_status_code || preparation.payment_status

  if (preparation.provider !== "WECHAT") {
    if (paymentStatus === "SUCCESS") {
      const order = await request<Order>(`/orders/${orderId}`, { userId })
      return { mode: "mock", order }
    }
    throw new Error("PAYMENT_PROVIDER_UNSUPPORTED")
  }

  if (paymentStatus === "SUCCESS") {
    return { mode: "wechat", alreadyConfirmed: true }
  }

  await requestWeChatPayment(asWeChatPayload(preparation.client_payload))
  return { mode: "wechat", alreadyConfirmed: false }
}
