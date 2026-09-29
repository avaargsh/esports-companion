import { request } from "./client"
import { isWeChatAuthMode } from "./config"
import type { Order } from "../types/domain"

type WeChatClientPayload = {
  timeStamp: string
  nonceStr: string
  package: string
  signType: "RSA" | string
  paySign: string
}

type PaymentPreparation = {
  order_id: string
  order_status: string
  provider: string
  payment_status: string
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

function requestWeChatPayment(payload: WeChatClientPayload): Promise<void> {
  return new Promise((resolve, reject) => {
    uni.requestPayment({
      timeStamp: payload.timeStamp,
      nonceStr: payload.nonceStr,
      package: payload.package,
      signType: payload.signType,
      paySign: payload.paySign,
      success() {
        resolve()
      },
      fail(result) {
        const message = String(result.errMsg || "")
        if (message.toLowerCase().includes("cancel")) {
          reject(new Error("PAYMENT_CANCELLED"))
          return
        }
        reject(new Error("WECHAT_REQUEST_PAYMENT_FAILED"))
      }
    })
  })
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

  if (preparation.provider !== "WECHAT") {
    throw new Error("WECHAT_PAYMENT_PROVIDER_REQUIRED")
  }

  if (preparation.payment_status === "SUCCESS") {
    return { mode: "wechat", alreadyConfirmed: true }
  }

  await requestWeChatPayment(asWeChatPayload(preparation.client_payload))
  return { mode: "wechat", alreadyConfirmed: false }
}
