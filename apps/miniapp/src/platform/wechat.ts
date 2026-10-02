export type WeChatPaymentPayload = {
  timeStamp: string
  nonceStr: string
  package: string
  signType: "RSA" | string
  paySign: string
}

export type SubscriptionMessageDecision =
  | "accept"
  | "reject"
  | "ban"
  | "filter"
  | string

type SubscribeMessageApi = {
  requestSubscribeMessage(options: {
    tmplIds: string[]
    success(result: Record<string, unknown>): void
    fail(result: { errMsg?: string }): void
  }): void
}

export function requestWeChatLoginCode(): Promise<string> {
  return new Promise((resolve, reject) => {
    uni.login({
      provider: "weixin",
      success(result) {
        if (result.code) {
          resolve(result.code)
          return
        }
        reject(new Error("WECHAT_LOGIN_CODE_MISSING"))
      },
      fail() {
        reject(new Error("WECHAT_LOGIN_FAILED"))
      }
    })
  })
}

export function requestWeChatPayment(
  payload: WeChatPaymentPayload
): Promise<void> {
  return new Promise((resolve, reject) => {
    uni.requestPayment({
      provider: "wxpay",
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

export function requestWeChatSubscriptionMessages(
  templateIds: string[]
): Promise<Record<string, SubscriptionMessageDecision>> {
  const ids = [...new Set(templateIds.map(item => item.trim()).filter(Boolean))]
  if (!ids.length) return Promise.resolve({})

  return new Promise((resolve, reject) => {
    const wechat = uni as unknown as SubscribeMessageApi
    wechat.requestSubscribeMessage({
      tmplIds: ids,
      success(result) {
        const decisions: Record<string, SubscriptionMessageDecision> = {}
        for (const id of ids) {
          const value = result[id]
          if (typeof value === "string") decisions[id] = value
        }
        resolve(decisions)
      },
      fail(result) {
        reject(
          new Error(
            String(result.errMsg || "WECHAT_SUBSCRIBE_MESSAGE_FAILED")
          )
        )
      }
    })
  })
}
