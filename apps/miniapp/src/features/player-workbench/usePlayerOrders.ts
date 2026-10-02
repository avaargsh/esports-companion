import { computed, ref } from "vue"

import { listPlayerOrders } from "../../domain/player/api"
import { getPlayerPrincipal } from "../../product/principal"
import { useAsyncStatus } from "../../shared/composables/useAsyncStatus"
import type { Order } from "../../types/domain"
import { showMessage } from "../../ui/feedback"
import { isActiveOrder } from "../../utils/order"

export type PlayerOrderFilter = "ACTIVE" | "DONE"

export function usePlayerOrders() {
  const orders = ref<Order[]>([])
  const filter = ref<PlayerOrderFilter>("ACTIVE")
  const refreshing = ref(false)
  const {
    status: loadStatus,
    message: loadMessage,
    start: startLoad,
    succeed: finishLoad,
    fail: failLoad
  } = useAsyncStatus("loading")

  const activeCount = computed(() =>
    orders.value.filter(item => isActiveOrder(item.status)).length
  )

  const doneCount = computed(() =>
    orders.value.length - activeCount.value
  )

  const visibleOrders = computed(() =>
    orders.value.filter(item =>
      filter.value === "ACTIVE"
        ? isActiveOrder(item.status)
        : !isActiveOrder(item.status)
    )
  )

  async function load(): Promise<void> {
    const hasContent = orders.value.length > 0
    if (hasContent) refreshing.value = true
    else startLoad()

    try {
      const principal = await getPlayerPrincipal()
      if (!principal) {
        orders.value = []
        finishLoad({ empty: true })
        return
      }

      orders.value = await listPlayerOrders(principal.userId)
      finishLoad({ empty: orders.value.length === 0 })
    } catch (error) {
      if (hasContent) {
        showMessage(
          error instanceof Error ? error.message : "服务订单刷新失败"
        )
      } else {
        failLoad(error, "服务订单加载失败")
      }
    } finally {
      refreshing.value = false
    }
  }

  return {
    orders,
    filter,
    refreshing,
    loadStatus,
    loadMessage,
    activeCount,
    doneCount,
    visibleOrders,
    load
  }
}
