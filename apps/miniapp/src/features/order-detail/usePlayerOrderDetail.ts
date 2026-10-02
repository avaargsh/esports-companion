import { computed, ref } from "vue"

import { isWeChatAuthMode } from "../../api/config"
import {
  getOrderDetail,
  listOrderEvents
} from "../../domain/order/api"
import {
  formatOrderTimestamp,
  isOrderChatVisible,
  isOrderChatWritable,
  playerActorLabel,
  playerCanOpenDispute,
  playerDemoJourney,
  playerEventTitle,
  playerIncomeCaption,
  playerPrimaryAction
} from "../../domain/order/presenter"
import {
  subscribeOrderRealtime,
  type OrderRealtimeSubscription
} from "../../domain/order/realtime"
import { getPlayerPrincipal } from "../../product/principal"
import { useAsyncStatus } from "../../shared/composables/useAsyncStatus"
import type { Order, OrderEvent } from "../../types/domain"
import { showMessage } from "../../ui/feedback"
import {
  orderStatusMeta,
  playerActionErrorMessage
} from "../../utils/order"
import { usePlayerOrderActions } from "./usePlayerOrderActions"

export function usePlayerOrderDetail() {
  const orderId = ref("")
  const order = ref<Order | null>(null)
  const events = ref<OrderEvent[]>([])
  const eventsExpanded = ref(false)
  const playerUserId = ref("")
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
    order.value ? orderStatusMeta(order.value.status, "PLAYER") : null
  )

  const incomeCaption = computed(() =>
    playerIncomeCaption(order.value?.status)
  )

  const demoJourney = computed(() =>
    playerDemoJourney(order.value?.status)
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
    playerPrimaryAction(order.value)
  )

  const canOpenDispute = computed(() =>
    playerCanOpenDispute(order.value)
  )

  async function reload({
    silent = false
  }: {
    silent?: boolean
  } = {}): Promise<boolean> {
    if (!orderId.value || !playerUserId.value) return false

    const hasContent = Boolean(order.value)
    if (!hasContent) startLoad()

    try {
      const [nextOrder, nextEvents] = await Promise.all([
        getOrderDetail(playerUserId.value, orderId.value),
        listOrderEvents(playerUserId.value, orderId.value)
      ])
      order.value = nextOrder
      events.value = nextEvents
      finishLoad()
      return true
    } catch (error) {
      const message = playerActionErrorMessage(
        error instanceof Error ? error.message : ""
      )
      if (hasContent) {
        if (!silent) showMessage(message)
      } else {
        failLoad(new Error(message), "服务单加载失败")
      }
      return false
    }
  }

  const {
    busy,
    aftercareReason,
    runPrimary,
    openDispute
  } = usePlayerOrderActions({
    order,
    userId: playerUserId,
    primaryAction,
    reload
  })

  async function connectRealtime(): Promise<void> {
    realtime?.close()
    realtime = null
    socketConnected.value = false

    if (!orderId.value || !playerUserId.value) return

    try {
      realtime = await subscribeOrderRealtime({
        orderId: orderId.value,
        userId: playerUserId.value,
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
      failLoad(new Error("服务单不存在或链接已失效"), "服务单加载失败")
      initialized.value = true
      return
    }

    try {
      const principal = await getPlayerPrincipal()
      if (!principal) {
        failLoad(new Error("当前账号还没有陪玩身份"), "服务单加载失败")
        return
      }

      playerUserId.value = principal.userId
      const loaded = await reload()
      if (loaded) await connectRealtime()
    } catch (error) {
      failLoad(
        new Error(
          playerActionErrorMessage(
            error instanceof Error ? error.message : ""
          )
        ),
        "服务单加载失败"
      )
    } finally {
      initialized.value = true
    }
  }

  async function refresh(): Promise<void> {
    if (!initialized.value) return
    await reload()
  }

  async function retry(): Promise<void> {
    if (!playerUserId.value) {
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
    playerUserId,
    socketConnected,
    busy,
    aftercareReason,
    chatRefreshKey,
    demoMode,
    loadStatus,
    loadMessage,
    meta,
    incomeCaption,
    demoJourney,
    visibleEvents,
    chatVisible,
    chatWritable,
    primaryAction,
    canOpenDispute,
    init,
    refresh,
    retry,
    dispose,
    runPrimary,
    openDispute,
    eventTitle: playerEventTitle,
    actorLabel: playerActorLabel,
    formatTime: formatOrderTimestamp
  }
}
