import { computed, ref } from "vue"

import { isWeChatAuthMode } from "../../api/config"
import { listGames } from "../../domain/catalog/api"
import {
  claimPlayerOrder,
  getPlayerProfile,
  listPlayerOrderPool,
  type PlayerPoolOrder,
  type PlayerProfile
} from "../../domain/player/api"
import { getPlayerPrincipal } from "../../product/principal"
import { useAsyncStatus } from "../../shared/composables/useAsyncStatus"
import type { Game, Order } from "../../types/domain"
import { showMessage, showSuccess } from "../../ui/feedback"
import { claimErrorMessage } from "../../utils/order"

export function usePlayerOrderPool() {
  const games = ref<Game[]>([])
  const gameId = ref("")
  const orders = ref<PlayerPoolOrder[]>([])
  const profile = ref<PlayerProfile | null>(null)
  const playerUserId = ref("")
  const claimingId = ref("")
  const initialized = ref(false)
  const demoMode = !isWeChatAuthMode()
  const {
    status: loadStatus,
    message: loadMessage,
    start: startLoad,
    succeed: finishLoad,
    fail: failLoad
  } = useAsyncStatus("loading")

  const bestIncome = computed(() =>
    orders.value.reduce((max, item) => Math.max(max, item.player_amount), 0)
  )
  const claimBlockReason = computed(() => {
    if (!profile.value) return "正在同步陪玩身份"
    if (profile.value.verification_status !== "APPROVED") {
      return "认证未通过，暂不可接单"
    }
    if (profile.value.available_actions.includes("GO_AVAILABLE")) {
      return "已暂停接单，请先回工作台开启接单"
    }
    return ""
  })

  function canClaim(order: Order): boolean {
    return order.available_actions?.includes("CLAIM_ORDER") ?? false
  }

  async function loadPool({ silent = false } = {}) {
    if (!gameId.value || !playerUserId.value) return false
    const hasContent = orders.value.length > 0
    if (!hasContent) startLoad()

    try {
      orders.value = await listPlayerOrderPool(
        playerUserId.value,
        gameId.value
      )
      finishLoad({ empty: orders.value.length === 0 })
      return true
    } catch (error) {
      const message = claimErrorMessage(
        error instanceof Error ? error.message : ""
      )
      if (hasContent) {
        if (!silent) showMessage(message)
      } else {
        failLoad(new Error(message), "抢单大厅加载失败")
      }
      return false
    }
  }

  async function bootstrap() {
    if (initialized.value) {
      await refresh()
      return
    }

    startLoad()
    try {
      const principal = await getPlayerPrincipal()
      if (!principal) throw new Error("PLAYER_PROFILE_NOT_FOUND")

      playerUserId.value = principal.userId
      const [nextProfile, nextGames] = await Promise.all([
        getPlayerProfile(principal.userId),
        listGames()
      ])
      profile.value = nextProfile
      games.value = nextGames

      if (!gameId.value && nextGames.length) {
        gameId.value = nextGames[0].id
      }
      await loadPool()
      initialized.value = true
    } catch (error) {
      failLoad(
        new Error(
          claimErrorMessage(error instanceof Error ? error.message : "")
        ),
        "抢单大厅加载失败"
      )
      initialized.value = true
    }
  }

  async function refresh() {
    if (!playerUserId.value) {
      initialized.value = false
      await bootstrap()
      return
    }

    try {
      profile.value = await getPlayerProfile(playerUserId.value)
      await loadPool()
    } catch (error) {
      showMessage(
        claimErrorMessage(error instanceof Error ? error.message : "")
      )
    }
  }

  async function selectGame(id: string) {
    if (gameId.value === id) return
    gameId.value = id
    orders.value = []
    await loadPool()
  }

  async function claim(order: PlayerPoolOrder): Promise<Order | null> {
    if (!playerUserId.value || claimingId.value) return null
    if (!canClaim(order)) {
      showMessage(claimBlockReason.value || "这笔订单当前不可抢")
      return null
    }

    claimingId.value = order.id
    try {
      const claimed = await claimPlayerOrder(
        playerUserId.value,
        order.id,
        order.version
      )
      showSuccess("接单成功")
      return claimed
    } catch (error) {
      showMessage(
        claimErrorMessage(error instanceof Error ? error.message : "")
      )
      await loadPool({ silent: true })
      return null
    } finally {
      claimingId.value = ""
    }
  }

  return {
    games,
    gameId,
    orders,
    profile,
    playerUserId,
    claimingId,
    demoMode,
    loadStatus,
    loadMessage,
    bestIncome,
    claimBlockReason,
    canClaim,
    bootstrap,
    refresh,
    loadPool,
    selectGame,
    claim
  }
}
