import { request } from "./client"
import { isWeChatAuthMode } from "./config"
import type { Order } from "../types/domain"

type PaymentPrepare = {
  order_id: string
  order_status: string
  provider: string
  payment_status: string
  client_payload: {
    timeStamp?: string
    nonceStr?: string
    package?: string
    signType?: "RSA"
    paySign?: string
  }
  replayed: boolean
}

export type PaymentResult = {
  order: Order
  awaitingProviderConfirmation: boolean
}

function requestPayment(payload: PaymentPrepare["client_payload"]): Promise<void> {
  const {
    timeStamp,
    nonceStr,
    package: packageValue,
    signType,
    paySign
  } = payload

  if (!timeStamp || !nonceStr || !packageValue || signType !== "RSA" || !paySign) {
    return Promise.reject(new Error("WECHAT_PAYMENT_CLIENT_PAYLOAD_INVALID"))
  }

  return new Promise((resolve, reject) => {
    uni.requestPayment({
      timeStamp,
      nonceStr,
      package: packageValue,
      signType,
      paySign,
      success() {
        resolve()
      },
      fail(result) {
        const message = String(result.errMsg || "")
        if (message.toLowerCase().includes("cancel")) {
          reject(new Error("PAYMENT_CANCELLED"))
          return
        }
        reject(new Error("WECHAT_PAYMENT_REQUEST_FAILED"))
      }
    })
  })
}

async function loadOrder(orderId: string, userId: string): Promise<Order> {
  return request<Order>(`/orders/${orderId}`, { userId })
}

function delay(milliseconds: number): Promise<void> {
  return new Promise(resolve => {
    setTimeout(resolve, milliseconds)
  })
}

async function waitForProviderConfirmation(
  orderId: string,
  userId: string
): Promise<PaymentResult> {
  let order = await loadOrder(orderId, userId)
  if (order.status !== "WAITING_PAYMENT") {
    return { order, awaitingProviderConfirmation: false }
  }

  for (let attempt = 0; attempt < 4; attempt += 1) {
    await delay(500)
    order = await loadOrder(orderId, userId)
    if (order.status !== "WAITING_PAYMENT") {
      return { order, awaitingProviderConfirmation: false }
    }
  }

  return { order, awaitingProviderConfirmation: true }
}

export async function submitOrderPayment(
  orderId: string,
  userId: string
): Promise<PaymentResult> {
  const idempotencyKey = `miniapp-payment-${orderId}`

  if (!isWeChatAuthMode()) {
    const order = await request<Order>(`/orders/${orderId}/mock-pay`, {
      method: "POST",
      userId,
      headers: { "Idempotency-Key": idempotencyKey }
    })
    return {
      order,
      awaitingProviderConfirmation: false
    }
  }

  const preparation = await request<PaymentPrepare>(
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
  if (preparation.order_id !== orderId) {
    throw new Error("PAYMENT_ORDER_MISMATCH")
  }
  if (
    preparation.payment_status === "SUCCESS" ||
    preparation.order_status !== "WAITING_PAYMENT"
  ) {
    return {
      order: await loadOrder(orderId, userId),
      awaitingProviderConfirmation: false
    }
  }

  await requestPayment(preparation.client_payload)
  return waitForProviderConfirmation(orderId, userId)
}
