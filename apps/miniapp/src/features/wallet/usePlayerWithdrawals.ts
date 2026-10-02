import { computed, ref, watch } from "vue"

import {
  getWallet,
  listWithdrawals,
  requestWithdrawal
} from "../../domain/wallet/api"
import {
  formatWithdrawalTime,
  pendingWithdrawalAmount,
  withdrawalStatusLabel
} from "../../domain/wallet/presenter"
import { setClipboardText } from "../../platform/clipboard"
import { getPlayerPrincipal } from "../../product/principal"
import { useAsyncStatus } from "../../shared/composables/useAsyncStatus"
import type { Wallet, Withdrawal } from "../../types/domain"
import { confirmAction, showMessage, showSuccess } from "../../ui/feedback"

export function usePlayerWithdrawals() {
  const userId = ref("")
  const wallet = ref<Wallet>({
    availableBalance: 0,
    frozenBalance: 0,
    availableActions: []
  })
  const items = ref<Withdrawal[]>([])
  const amountYuan = ref("")
  const busy = ref(false)
  const pendingIdempotencyKey = ref("")
  const initialized = ref(false)
  const {
    status: loadStatus,
    message: loadMessage,
    start: startLoad,
    succeed: finishLoad,
    fail: failLoad
  } = useAsyncStatus("loading")

  const amountCents = computed(() => {
    const value = Number(amountYuan.value)
    if (!Number.isFinite(value) || value <= 0) return 0
    return Math.round(value * 100)
  })

  const requestEnabled = computed(() =>
    wallet.value.availableActions?.includes("REQUEST_WITHDRAWAL") ?? false
  )

  const canSubmit = computed(() =>
    requestEnabled.value &&
    amountCents.value > 0 &&
    amountCents.value <= wallet.value.availableBalance &&
    !busy.value
  )

  const pendingAmount = computed(() =>
    pendingWithdrawalAmount(items.value)
  )

  watch(amountYuan, () => {
    pendingIdempotencyKey.value = ""
  })

  async function load({ silent = false } = {}) {
    const hasContent = initialized.value
    if (!hasContent) startLoad()

    try {
      if (!userId.value) {
        const principal = await getPlayerPrincipal()
        if (!principal) throw new Error("PLAYER_REQUIRED")
        userId.value = principal.userId
      }

      const [nextWallet, nextItems] = await Promise.all([
        getWallet(userId.value),
        listWithdrawals(userId.value)
      ])
      wallet.value = nextWallet
      items.value = nextItems
      initialized.value = true
      finishLoad()
      return true
    } catch (error) {
      if (hasContent) {
        if (!silent) {
          showMessage(
            error instanceof Error ? error.message : "提现信息刷新失败"
          )
        }
      } else {
        failLoad(error, "提现信息加载失败")
      }
      return false
    }
  }

  async function submit() {
    if (!canSubmit.value || !userId.value) return

    const amountText = (amountCents.value / 100).toFixed(2)
    const confirmed = await confirmAction({
      title: `确认提现 ¥${amountText}？`,
      content: "提交后该金额会从可用余额转入冻结，等待平台审核和打款。",
      confirmText: "确认提现"
    })
    if (!confirmed) return

    if (!pendingIdempotencyKey.value) {
      pendingIdempotencyKey.value =
        `miniapp-withdraw-${Date.now()}-${amountCents.value}`
    }

    busy.value = true
    try {
      const created = await requestWithdrawal(
        userId.value,
        amountCents.value,
        pendingIdempotencyKey.value
      )
      amountYuan.value = ""
      pendingIdempotencyKey.value = ""
      showSuccess(`提现申请已提交 ${created.id.slice(0, 8)}`)
      await load({ silent: true })
    } catch (error) {
      showMessage(
        error instanceof Error ? error.message : "提交失败，可直接重试"
      )
      await load({ silent: true })
    } finally {
      busy.value = false
    }
  }

  function withdrawAll() {
    if (!requestEnabled.value) return
    amountYuan.value = (wallet.value.availableBalance / 100).toFixed(2)
  }

  async function copyValue(value: string, label: string) {
    try {
      await setClipboardText(value)
      showMessage(`${label}已复制`)
    } catch {
      showMessage("复制失败，请手动记录")
    }
  }

  return {
    wallet,
    items,
    amountYuan,
    busy,
    loadStatus,
    loadMessage,
    amountCents,
    requestEnabled,
    canSubmit,
    pendingAmount,
    load,
    submit,
    withdrawAll,
    copyValue,
    statusLabel: withdrawalStatusLabel,
    formatTime: formatWithdrawalTime
  }
}
