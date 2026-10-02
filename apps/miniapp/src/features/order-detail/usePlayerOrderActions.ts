import {
  ref,
  type ComputedRef,
  type Ref
} from "vue"

import {
  createOrderAftercare,
  finishPlayerOrder,
  startPlayerOrder
} from "../../domain/order/api"
import type { PlayerPrimaryAction } from "../../domain/order/presenter"
import type { Order } from "../../types/domain"
import { confirmAction, showMessage, showSuccess } from "../../ui/feedback"
import { playerActionErrorMessage } from "../../utils/order"

type ReloadOrderDetail = (
  options?: { silent?: boolean }
) => Promise<boolean>

export function usePlayerOrderActions({
  order,
  userId,
  primaryAction,
  reload
}: {
  order: Ref<Order | null>
  userId: Ref<string>
  primaryAction: ComputedRef<PlayerPrimaryAction | null>
  reload: ReloadOrderDetail
}) {
  const busy = ref(false)
  const aftercareReason = ref("")

  async function runPrimary(): Promise<void> {
    const current = order.value
    const action = primaryAction.value
    if (!current || !action || busy.value || !userId.value) return

    if (action.kind === "finish") {
      const confirmed = await confirmAction({
        title: "申请完成本次服务？",
        content: "提交后将等待用户确认；如果服务存在争议，请先申请平台介入。",
        confirmText: "申请完成"
      })
      if (!confirmed) return
    }

    busy.value = true
    try {
      if (action.kind === "start") {
        await startPlayerOrder(userId.value, current.id)
        showSuccess("服务已开始")
      } else {
        await finishPlayerOrder(userId.value, current.id)
        showSuccess("已申请完成")
      }
      await reload({ silent: true })
    } catch (error) {
      showMessage(
        playerActionErrorMessage(
          error instanceof Error ? error.message : ""
        )
      )
      await reload({ silent: true })
    } finally {
      busy.value = false
    }
  }

  async function openDispute(): Promise<void> {
    const current = order.value
    if (!current || busy.value || !userId.value) return

    const confirmed = await confirmAction({
      title: "申请平台介入？",
      content: "平台会根据订单状态、沟通记录与双方说明处理争议，处理期间请停止继续履约。",
      confirmText: "申请介入",
      tone: "brand"
    })
    if (!confirmed) return

    busy.value = true
    try {
      await createOrderAftercare(
        userId.value,
        current.id,
        "dispute",
        aftercareReason.value.trim()
      )
      aftercareReason.value = ""
      showSuccess("已申请平台介入")
      await reload({ silent: true })
    } catch (error) {
      showMessage(
        playerActionErrorMessage(
          error instanceof Error ? error.message : ""
        )
      )
    } finally {
      busy.value = false
    }
  }

  return {
    busy,
    aftercareReason,
    runPrimary,
    openDispute
  }
}
