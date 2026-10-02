import { computed, ref } from "vue"

import { isWeChatAuthMode } from "../../api/config"
import {
  getOrderDetail,
  listOrderEvents
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
import { getCustomerPrincipal } from "../../product/principal"
import { useAsyncStatus } from "../../shared/composables/useAsyncStatus"
import type { Order, OrderEvent } from "../../types/domain"
import { showMessage } from "../../ui/feedback"
import { orderStatusMeta } from "../../utils/order"
import { useCustomerOrderActions } from "./useCustomerOrderActions"

export function useCustomerOrderDetail() {
  const orderId = ref("")
  const order = ref<Order | null>(null)
  const events = ref<OrderEvent[]>([])
  const eventsExpanded = ref(false)
  const customerUserId = ref("")
  const socketConnected = ref(false)
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

  const {
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
  } = useCustomerOrderActions({
    order,
    userId: customerUserId,
    primaryAction,
    reload
  })

  const demoJourney = computed(() =>
    customerDemoJourney(order.value?.status, reviewed.value)
  )

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
