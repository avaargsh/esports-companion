import { ref } from "vue"

import { isWeChatAuthMode } from "../../api/config"
import { listGames } from "../../domain/catalog/api"
import { listPublicPlayers } from "../../domain/marketplace/api"
import { useAsyncStatus } from "../../shared/composables/useAsyncStatus"
import type { Game, PublicPlayer } from "../../types/domain"
import { showMessage } from "../../ui/feedback"

export function useHomeDiscovery() {
  const games = ref<Game[]>([])
  const players = ref<PublicPlayer[]>([])
  const initialized = ref(false)
  const demoMode = !isWeChatAuthMode()
  const {
    status: loadStatus,
    message: loadMessage,
    start: startLoad,
    succeed: finishLoad,
    fail: failLoad
  } = useAsyncStatus("loading")

  async function load({ silent = false } = {}) {
    const hasContent = initialized.value
    if (!hasContent) startLoad()

    try {
      const [gameItems, playerItems] = await Promise.all([
        listGames(),
        listPublicPlayers({ limit: 4 })
      ])
      games.value = gameItems
      players.value = playerItems
      initialized.value = true
      finishLoad({ empty: gameItems.length === 0 })
      return true
    } catch (error) {
      if (hasContent) {
        if (!silent) showMessage("首页刷新失败")
      } else {
        failLoad(error, "服务暂时没加载出来")
      }
      return false
    }
  }

  return {
    games,
    players,
    demoMode,
    loadStatus,
    loadMessage,
    load
  }
}
