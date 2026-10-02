import { computed, ref } from "vue"

import { isWeChatAuthMode } from "../../api/config"
import {
  getPlayerProfile,
  listPlayerOrders,
  updatePlayerServiceStatus,
  type PlayerProfile
} from "../../domain/player/api"
import { getWallet } from "../../domain/wallet/api"
import { getPlayerPrincipal, type ProductPrincipal } from "../../product/principal"
import { useAsyncStatus } from "../../shared/composables/useAsyncStatus"
import type { Order, Wallet } from "../../types/domain"
import { showMessage } from "../../ui/feedback"

export function usePlayerWorkbench() {
  const profile = ref<PlayerProfile | null>(null)
  const wallet = ref<Wallet>({ availableBalance: 0, frozenBalance: 0 })
  const orders = ref<Order[]>([])
  const principal = ref<ProductPrincipal | null>(null)
  const busy = ref(false)
  const refreshing = ref(false)
  const demoMode = !isWeChatAuthMode()
  const {
    status: loadStatus,
    message: loadMessage,
    start: startLoad,
    succeed: finishLoad,
    fail: failLoad
  } = useAsyncStatus("loading")

  const online = computed(() => profile.value?.service_status === "AVAILABLE")
  const serviceAction = computed(() => {
    const actions = profile.value?.available_actions ?? []
    if (actions.includes("GO_OFFLINE")) return "GO_OFFLINE" as const
    if (actions.includes("GO_AVAILABLE")) return "GO_AVAILABLE" as const
    return null
  })
  const acceptedCount = computed(() =>
    orders.value.filter(item => item.status === "ACCEPTED").length
  )
  const inServiceCount = computed(() =>
    orders.value.filter(item => item.status === "IN_SERVICE").length
  )
  const waitingConfirmCount = computed(() =>
    orders.value.filter(item => item.status === "FINISH_REQUESTED").length
  )
  const activeIncome = computed(() =>
    orders.value
      .filter(item =>
        ["ACCEPTED", "IN_SERVICE", "FINISH_REQUESTED"].includes(item.status)
      )
      .reduce((sum, item) => sum + item.player_amount, 0)
  )

  async function load() {
    const hasContent = Boolean(profile.value)
    if (hasContent) refreshing.value = true
    else startLoad()

    try {
      const nextPrincipal = await getPlayerPrincipal()
      if (!nextPrincipal) {
        principal.value = null
        profile.value = null
        orders.value = []
        wallet.value = { availableBalance: 0, frozenBalance: 0 }
        finishLoad({ empty: true })
        return
      }

      const [nextProfile, nextWallet, nextOrders] = await Promise.all([
        getPlayerProfile(nextPrincipal.userId),
        getWallet(nextPrincipal.userId),
        listPlayerOrders(nextPrincipal.userId)
      ])

      principal.value = nextPrincipal
      profile.value = nextProfile
      wallet.value = nextWallet
      orders.value = nextOrders
      finishLoad()
    } catch (error) {
      if (hasContent) {
        showMessage(error instanceof Error ? error.message : "工作台刷新失败")
      } else {
        failLoad(error, "陪玩工作台加载失败")
      }
    } finally {
      refreshing.value = false
    }
  }

  async function toggleServiceStatus() {
    if (!profile.value || !principal.value || busy.value) return
    const action = serviceAction.value
    if (!action) {
      showMessage("当前身份暂不能修改接单状态")
      return
    }

    busy.value = true
    try {
      profile.value = await updatePlayerServiceStatus(
        principal.value.userId,
        action === "GO_OFFLINE" ? "OFFLINE" : "AVAILABLE"
      )
    } catch (error) {
      showMessage(error instanceof Error ? error.message : "状态切换失败")
      await load()
    } finally {
      busy.value = false
    }
  }

  return {
    profile,
    wallet,
    orders,
    principal,
    busy,
    refreshing,
    demoMode,
    loadStatus,
    loadMessage,
    online,
    serviceAction,
    acceptedCount,
    inServiceCount,
    waitingConfirmCount,
    activeIncome,
    load,
    toggleServiceStatus
  }
}
