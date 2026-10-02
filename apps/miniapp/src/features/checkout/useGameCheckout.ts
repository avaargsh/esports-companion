import { computed, ref } from "vue"

import { isWeChatAuthMode } from "../../api/config"
import { listGameSkus } from "../../domain/catalog/api"
import { createCustomerOrder } from "../../domain/order/api"
import { getCustomerPrincipal } from "../../product/principal"
import { useAsyncStatus } from "../../shared/composables/useAsyncStatus"
import type { Order, ServiceSku } from "../../types/domain"
import { showMessage } from "../../ui/feedback"

export function useGameCheckout() {
  const gameId = ref("")
  const gameName = ref("选择服务")
  const skus = ref<ServiceSku[]>([])
  const selectedId = ref("")
  const remark = ref("")
  const quantity = ref(1)
  const creating = ref(false)
  const demoMode = !isWeChatAuthMode()
  const {
    status: loadStatus,
    message: loadMessage,
    start: startLoad,
    succeed: finishLoad,
    fail: failLoad
  } = useAsyncStatus("loading")

  const selected = computed(() =>
    skus.value.find(item => item.id === selectedId.value) ?? null
  )

  const totalAmount = computed(() =>
    (selected.value?.price || 0) * quantity.value
  )

  const canCreate = computed(() =>
    selected.value?.available_actions?.includes("CREATE_ORDER") ?? false
  )

  function changeQuantity(delta: number) {
    quantity.value = Math.min(10, Math.max(1, quantity.value + delta))
  }

  async function loadSkus() {
    if (!gameId.value) {
      failLoad(new Error("GAME_ID_REQUIRED"), "游戏信息无效")
      return false
    }

    startLoad()
    try {
      skus.value = await listGameSkus(gameId.value)
      selectedId.value = skus.value[0]?.id ?? ""
      finishLoad({ empty: skus.value.length === 0 })
      return true
    } catch (error) {
      failLoad(error, "服务加载失败")
      return false
    }
  }

  async function init(id: string, name: string) {
    gameId.value = id
    gameName.value = name || "选择服务"
    await loadSkus()
  }

  async function createOrder(): Promise<Order | null> {
    if (!selected.value || !canCreate.value || creating.value) return null

    creating.value = true
    try {
      const principal = await getCustomerPrincipal()
      return await createCustomerOrder(principal.userId, {
        skuId: selected.value.id,
        quantity: quantity.value,
        remark: remark.value.trim()
      })
    } catch (error) {
      showMessage(error instanceof Error ? error.message : "下单失败")
      await loadSkus()
      return null
    } finally {
      creating.value = false
    }
  }

  return {
    gameName,
    skus,
    selectedId,
    remark,
    quantity,
    creating,
    demoMode,
    loadStatus,
    loadMessage,
    selected,
    totalAmount,
    canCreate,
    changeQuantity,
    loadSkus,
    init,
    createOrder
  }
}
