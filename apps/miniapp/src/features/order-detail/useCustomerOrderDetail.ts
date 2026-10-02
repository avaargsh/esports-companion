import { computed, ref } from "vue"

import { isWeChatAuthMode } from "../../api/config"
import { startOrderPayment } from "../../api/payment"
import {
  cancelCustomerOrder,
  confirmCustomerOrder,
  createOrderAftercare,
  getOrderDetail,
  listOrderEvents,
  submitOrderReview,
  type OrderAftercareKind
} from "../../domain/order/api"
import {
  customerActorLabel,
  customerDemoJourney,
  customerEventTitle,
  customerPrimaryAction,
  customerSecondaryAction,
  formatOrderTimestamp,
  isOrderChatVisible,
  isOrderChatWritable
} from "../../domain/order/presenter"
import {
  subscribeOrderRealtime,
  type OrderRealtimeSubscription
} from "../../domain/order/realtime"
import { navigation } from "../../platform/navigation"
import { getCustomerPrincipal } from "../../product/principal"
import { useAsyncStatus } from "../../shared/composables/useAsyncStatus"
import type { Order, OrderEvent } from "../../types/domain"
import { confirmAction, showMessage, showSuccess } from "../../ui/feedback"
import { orderStatusMeta } from "../../utils/order"

const PAYMENT_CONFIRM_ATTEMPTS = 8
const PAYMENT_CONFIRM_INTERVAL_MS = 750

export function useCustomerOrderDetail() {
  const orderId = ref("")
  const order = ref<Order | null>(null)
  const events = ref<OrderEvent[]>([])
  const eventsExpanded = ref(false)
  const customerUserId = ref("")
  const socketConnected = ref(false)
  const busy = ref(false)
  const rating = ref(5)
  const review = ref("")
  const reviewed = ref(false)
  const aftercareReason = ref("")
  const chatRefreshKey = ref(0)
  const initialized = ref(false)
  const demoMode = !isWeChatAuthMode()
  const {
    status: loadStatus,
    message: loadMessage,
    start: startLoad,
    succeed: finishLoad,
    fail: failLoad
  } = useAsyncStatus("loading")

  let realtime: OrderRealtimeSubscription | null = null

  const meta = computed(() =>
    order.value ? orderStatusMeta(order.value.status, "CUSTOMER") : null
  )

  const demoJourney = computed(() =>
    customerDemoJourney(order.value?.status, reviewed.value)
  )

  const visibleEvents = computed(() =>
    eventsExpanded.value || events.value.length <= 4
      ? events.value
      : events.value.slice(-4)
  )

  const chatVisible = computed(() =>
    isOrderChatVisible(order.value?.status)
  )

  const chatWritable = computed(() =>
    isOrderChatWritable(order.value?.status)
  )

  const primaryAction = computed(() =>
    customerPrimaryAction(order.value)
  )

  const secondaryAction = computed(() =>
    customerSecondaryAction(order.value)
  )

  async function reload({
    silent = false
  }: {
    silent?: boolean
  } = {}): Promise<boolean> {
    if (!orderId.value || !customerUserId.value) return false

    const hasContent = Boolean(order.value)
    if (!hasContent) startLoad()

    try {
      const [nextOrder, nextEvents] = await Promise.all([
        getOrderDetail(customerUserId.value, orderId.value),
        listOrderEvents(customerUserId.value, orderId.value)
      ])
      order.value = nextOrder
      events.value = nextEvents
      finishLoad()
      return true
    } catch (error) {
      if (hasContent) {
        if (!silent) {
          showMessage(error instanceof Error ? error.message : "订单刷新失败")
        }
      } else {
        failLoad(error, "订单加载失败")
      }
      return false
    }
  }

  async function connectRealtime(): Promise<void> {
    realtime?.close()
    realtime = null
    socketConnected.value = false

    if (!orderId.value || !customerUserId.value) return

    try {
      realtime = await subscribeOrderRealtime({
        orderId: orderId.value,
        userId: customerUserId.value,
        handlers: {
          onConnectionChange(connected) {
            socketConnected.value = connected
          },
          onStatusChanged() {
            void reload({ silent: true })
          },
          onMessageCreated() {
            chatRefreshKey.value += 1
          }
        }
      })
    } catch {
      socketConnected.value = false
    }
  }

  async function init(id: string): Promise<void> {
    initialized.value = false
    orderId.value = id
    order.value = null
    events.value = []
    startLoad()

    if (!id) {
      failLoad(new Error("ORDER_ID_REQUIRED"), "订单不存在或链接已失效")
      initialized.value = true
      return
    }

    try {
      const principal = await getCustomerPrincipal()
      customerUserId.value = principal.userId
      const loaded = await reload()
      if (loaded) await connectRealtime()
    } catch (error) {
      failLoad(error, "订单加载失败")
    } finally {
      initialized.value = true
    }
  }

  async function refresh(): Promise<void> {
    if (!initialized.value) return
    await reload()
  }

  async function retry(): Promise<void> {
    if (!customerUserId.value) {
      await init(orderId.value)
      return
    }

    const loaded = await reload()
    if (loaded && !realtime) await connectRealtime()
  }

  function dispose(): void {
    realtime?.close()
    realtime = null
  }

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
    if (!current || !action || busy.value || !customerUserId.value) return

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
        const result = await startOrderPayment(
          current.id,
          customerUserId.value
        )
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
        await confirmCustomerOrder(customerUserId.value, current.id)
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
    if (!current || busy.value || !customerUserId.value) return

    const confirmed = await confirmAction({
      title: "取消订单？",
      content: "取消后订单将不再继续履约，相关资金会按当前订单规则处理。",
      confirmText: "确认取消",
      tone: "danger"
    })
    if (!confirmed) return

    busy.value = true
    try {
      await cancelCustomerOrder(customerUserId.value, current.id)
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
    if (!current || busy.value || !customerUserId.value) return

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
        customerUserId.value,
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
    if (
      !current ||
      reviewed.value ||
      busy.value ||
      !customerUserId.value
    ) {
      return
    }

    busy.value = true
    try {
      await submitOrderReview(
        customerUserId.value,
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
    order,
    events,
    eventsExpanded,
    customerUserId,
    socketConnected,
    busy,
    rating,
    review,
    reviewed,
    aftercareReason,
    chatRefreshKey,
    demoMode,
    loadStatus,
    loadMessage,
    meta,
    demoJourney,
    visibleEvents,
    chatVisible,
    chatWritable,
    primaryAction,
    secondaryAction,
    init,
    refresh,
    retry,
    dispose,
    runPrimary,
    cancelOrder,
    requestAftercare,
    submitReview,
    openServicePlayer,
    eventTitle: customerEventTitle,
    actorLabel: customerActorLabel,
    formatTime: formatOrderTimestamp
  }
}
