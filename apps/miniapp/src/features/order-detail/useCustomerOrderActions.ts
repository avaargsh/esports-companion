import {
  ref,
  type ComputedRef,
  type Ref
} from "vue"

import { startOrderPayment } from "../../api/payment"
import {
  cancelCustomerOrder,
  confirmCustomerOrder,
  createOrderAftercare,
  submitOrderReview,
  type OrderAftercareKind
} from "../../domain/order/api"
import type { CustomerPrimaryAction } from "../../domain/order/presenter"
import { navigation } from "../../platform/navigation"
import type { Order } from "../../types/domain"
import { confirmAction, showMessage, showSuccess } from "../../ui/feedback"

const PAYMENT_CONFIRM_ATTEMPTS = 8
const PAYMENT_CONFIRM_INTERVAL_MS = 750

type ReloadOrderDetail = (
  options?: { silent?: boolean }
) => Promise<boolean>

export function useCustomerOrderActions({
  order,
  userId,
  primaryAction,
  reload
}: {
  order: Ref<Order | null>
  userId: Ref<string>
  primaryAction: ComputedRef<CustomerPrimaryAction | null>
  reload: ReloadOrderDetail
}) {
  const busy = ref(false)
  const rating = ref(5)
  const review = ref("")
  const reviewed = ref(false)
  const aftercareReason = ref("")

  function sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }

  async function waitForPaymentConfirmation(): Promise<boolean> {
    for (let attempt = 0; attempt < PAYMENT_CONFIRM_ATTEMPTS; attempt += 1) {
      if (attempt > 0) await sleep(PAYMENT_CONFIRM_INTERVAL_MS)
      await reload({ silent: true })
      if (order.value && order.value.status !== "WAITING_PAYMENT") {
        return true
      }
    }
    return false
  }

  function navigateAgain(current: Order): void {
    if (current.service_player?.id) {
      navigation.push("/pages/player/index", {
        id: current.service_player.id
      })
      return
    }
    if (current.game_id) {
      navigation.push("/pages/game/index", {
        id: current.game_id
      })
      return
    }
    navigation.tab("/pages/home/index")
  }

  async function runPrimary(): Promise<void> {
    const current = order.value
    const action = primaryAction.value
    if (!current || !action || busy.value || !userId.value) return

    if (action.kind === "again") {
      navigateAgain(current)
      return
    }

    if (action.kind === "confirm") {
      const confirmed = await confirmAction({
        title: "确认服务已完成？",
        content: "确认后订单将进入结算流程；如果服务存在问题，请先申请退款或平台介入。",
        confirmText: "确认完成"
      })
      if (!confirmed) return
    }

    busy.value = true
    try {
      if (action.kind === "pay") {
        const result = await startOrderPayment(current.id, userId.value)
        if (result.mode === "mock") {
          order.value = result.order
          showSuccess("支付成功")
        } else {
          const confirmed =
            result.alreadyConfirmed || await waitForPaymentConfirmation()
          if (confirmed) showSuccess("支付已确认")
          else showMessage("支付结果确认中，请稍后刷新", 2600)
        }
      }

      if (action.kind === "confirm") {
        await confirmCustomerOrder(userId.value, current.id)
        showSuccess("已确认完成")
      }

      await reload({ silent: true })
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "操作失败，请刷新后重试"
      showMessage(message === "PAYMENT_CANCELLED" ? "已取消支付" : message)
      await reload({ silent: true })
    } finally {
      busy.value = false
    }
  }

  async function cancelOrder(): Promise<void> {
    const current = order.value
    if (!current || busy.value || !userId.value) return

    const confirmed = await confirmAction({
      title: "取消订单？",
      content: "取消后订单将不再继续履约，相关资金会按当前订单规则处理。",
      confirmText: "确认取消",
      tone: "danger"
    })
    if (!confirmed) return

    busy.value = true
    try {
      await cancelCustomerOrder(userId.value, current.id)
      showSuccess("订单已取消")
      await reload({ silent: true })
    } catch (error) {
      showMessage(error instanceof Error ? error.message : "取消失败")
      await reload({ silent: true })
    } finally {
      busy.value = false
    }
  }

  async function requestAftercare(
    action: OrderAftercareKind
  ): Promise<void> {
    const current = order.value
    if (!current || busy.value || !userId.value) return

    const confirmed = await confirmAction({
      title: action === "refund" ? "提交退款申请？" : "申请平台介入？",
      content:
        action === "refund"
          ? "提交后订单会进入平台处理流程，资金结算可能暂停。"
          : "平台介入后会根据订单记录和双方信息处理争议，资金结算可能暂停。",
      confirmText: action === "refund" ? "提交退款" : "申请介入",
      tone: action === "refund" ? "danger" : "brand"
    })
    if (!confirmed) return

    busy.value = true
    try {
      await createOrderAftercare(
        userId.value,
        current.id,
        action,
        aftercareReason.value.trim()
      )
      aftercareReason.value = ""
      showSuccess(action === "refund" ? "退款申请已提交" : "已申请平台介入")
      await reload({ silent: true })
    } catch (error) {
      showMessage(error instanceof Error ? error.message : "提交失败")
    } finally {
      busy.value = false
    }
  }

  async function submitReview(): Promise<void> {
    const current = order.value
    if (!current || reviewed.value || busy.value || !userId.value) return

    busy.value = true
    try {
      await submitOrderReview(
        userId.value,
        current.id,
        rating.value,
        review.value.trim()
      )
      reviewed.value = true
      showSuccess("评价已提交")
    } catch (error) {
      const message = error instanceof Error ? error.message : "评价失败"
      if (message.includes("ORDER_ALREADY_REVIEWED")) {
        reviewed.value = true
      }
      showMessage(message)
    } finally {
      busy.value = false
    }
  }

  function openServicePlayer(): void {
    const playerId = order.value?.service_player?.id
    if (!playerId) return
    navigation.push("/pages/player/index", { id: playerId })
  }

  return {
    busy,
    rating,
    review,
    reviewed,
    aftercareReason,
    runPrimary,
    cancelOrder,
    requestAftercare,
    submitReview,
    openServicePlayer
  }
}
