import { ref } from "vue"

import { isWeChatAuthMode } from "../../api/config"
import {
  applyPlayer,
  getPlayerProfile,
  type PlayerProfile
} from "../../domain/player/api"
import {
  getCustomerPrincipal,
  getPlayerPrincipal
} from "../../product/principal"
import { showMessage, showSuccess } from "../../ui/feedback"

export function useProfileIdentity() {
  const wechatMode = isWeChatAuthMode()
  const nickname = ref(wechatMode ? "微信用户" : "Demo Customer")
  const userId = ref("")
  const playerName = ref("")
  const playerProfile = ref<PlayerProfile | null>(null)
  const playerChecked = ref(!wechatMode)
  const applyOpen = ref(false)
  const applyName = ref("")
  const applyBio = ref("")
  const applying = ref(false)

  async function loadIdentity(): Promise<void> {
    try {
      const customer = await getCustomerPrincipal()
      userId.value = customer.userId
      nickname.value =
        customer.nickname || (wechatMode ? "微信用户" : "Demo Customer")

      if (!wechatMode) {
        const player = await getPlayerPrincipal()
        playerName.value = player?.displayName ?? ""
        playerChecked.value = true
        return
      }

      try {
        playerProfile.value = await getPlayerProfile(customer.userId)
        playerName.value = playerProfile.value.display_name
      } catch (error) {
        const message = error instanceof Error ? error.message : ""
        if (message !== "PLAYER_PROFILE_NOT_FOUND") throw error
        playerProfile.value = null
        playerName.value = ""
      } finally {
        playerChecked.value = true
      }
    } catch (error) {
      showMessage(error instanceof Error ? error.message : "账户加载失败")
    }
  }

  async function submitApplication(): Promise<boolean> {
    if (!wechatMode || !userId.value || applying.value) return false

    const displayName = applyName.value.trim()
    if (!displayName) {
      showMessage("请填写陪玩昵称")
      return false
    }

    applying.value = true
    try {
      playerProfile.value = await applyPlayer(
        userId.value,
        displayName,
        applyBio.value.trim()
      )
      playerName.value = playerProfile.value.display_name
      applyOpen.value = false
      showSuccess("申请已提交")
      return true
    } catch (error) {
      showMessage(error instanceof Error ? error.message : "申请提交失败")
      return false
    } finally {
      applying.value = false
    }
  }

  return {
    wechatMode,
    nickname,
    userId,
    playerName,
    playerProfile,
    playerChecked,
    applyOpen,
    applyName,
    applyBio,
    applying,
    loadIdentity,
    submitApplication
  }
}
