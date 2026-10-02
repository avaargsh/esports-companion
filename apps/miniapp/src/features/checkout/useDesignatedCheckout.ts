import { computed, ref } from "vue"

import { getPublicPlayer } from "../../domain/marketplace/api"
import { createCustomerOrder } from "../../domain/order/api"
import { getCustomerPrincipal } from "../../product/principal"
import { useAsyncStatus } from "../../shared/composables/useAsyncStatus"
import type {
  Order,
  PublicOffering,
  PublicPlayer
} from "../../types/domain"
import { showMessage } from "../../ui/feedback"

export function useDesignatedCheckout() {
  const playerId = ref("")
  const player = ref<PublicPlayer | null>(null)
  const selectedOfferingId = ref("")
  const remark = ref("")
  const quantity = ref(1)
  const creating = ref(false)
  const {
    status: loadStatus,
    message: loadMessage,
    start: startLoad,
    succeed: finishLoad,
    fail: failLoad
  } = useAsyncStatus("loading")

  const selectedOffering = computed<PublicOffering | null>(() =>
    player.value?.offerings.find(
      item => item.id === selectedOfferingId.value
    ) ?? null
  )

  const totalAmount = computed(() =>
    (selectedOffering.value?.price || 0) * quantity.value
  )

  const canCreate = computed(() =>
    player.value?.available_actions?.includes(
      "CREATE_DESIGNATED_ORDER"
    ) ?? false
  )

  function changeQuantity(delta: number) {
    quantity.value = Math.min(10, Math.max(1, quantity.value + delta))
  }

  async function loadPlayer() {
    if (!playerId.value) {
      failLoad(new Error("PLAYER_ID_REQUIRED"), "大神资料加载失败")
      return false
    }

    startLoad()
    try {
      player.value = await getPublicPlayer(playerId.value)
      selectedOfferingId.value = player.value.offerings[0]?.id ?? ""
      finishLoad()
      return true
    } catch (error) {
      failLoad(error, "大神资料加载失败")
      return false
    }
  }

  async function init(id: string) {
    playerId.value = id
    await loadPlayer()
  }

  async function createOrder(): Promise<Order | null> {
    if (
      !selectedOffering.value ||
      !canCreate.value ||
      creating.value
    ) {
      return null
    }

    creating.value = true
    try {
      const principal = await getCustomerPrincipal()
      return await createCustomerOrder(principal.userId, {
        offeringId: selectedOffering.value.id,
        quantity: quantity.value,
        remark: remark.value.trim()
      })
    } catch (error) {
      showMessage(error instanceof Error ? error.message : "下单失败")
      await loadPlayer()
      return null
    } finally {
      creating.value = false
    }
  }

  return {
    player,
    selectedOfferingId,
    remark,
    quantity,
    creating,
    loadStatus,
    loadMessage,
    selectedOffering,
    totalAmount,
    canCreate,
    changeQuantity,
    loadPlayer,
    init,
    createOrder
  }
}
