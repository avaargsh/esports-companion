import { ref } from "vue"

import { listGames } from "../../domain/catalog/api"
import { listPublicPlayers } from "../../domain/marketplace/api"
import { useAsyncStatus } from "../../shared/composables/useAsyncStatus"
import type { Game, PublicPlayer } from "../../types/domain"

export function usePlayerDiscovery() {
  const games = ref<Game[]>([])
  const players = ref<PublicPlayer[]>([])
  const selectedGameId = ref("")
  const {
    status: loadStatus,
    message: loadMessage,
    start: startLoad,
    succeed: finishLoad,
    fail: failLoad
  } = useAsyncStatus("loading")

  async function loadPlayers() {
    startLoad()
    try {
      players.value = await listPublicPlayers({
        gameId: selectedGameId.value || undefined,
        limit: 30
      })
      finishLoad({ empty: players.value.length === 0 })
      return true
    } catch (error) {
      players.value = []
      failLoad(error, "陪玩列表加载失败")
      return false
    }
  }

  async function init(gameId = "") {
    selectedGameId.value = gameId
    startLoad()
    try {
      games.value = await listGames()
      await loadPlayers()
    } catch (error) {
      failLoad(error, "陪玩列表加载失败")
    }
  }

  async function selectGame(id: string) {
    if (selectedGameId.value === id) return
    selectedGameId.value = id
    await loadPlayers()
  }

  return {
    games,
    players,
    selectedGameId,
    loadStatus,
    loadMessage,
    init,
    loadPlayers,
    selectGame
  }
}
