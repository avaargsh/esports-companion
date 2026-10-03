import { computed, ref } from "vue"

import { getStoredSession, logoutSession } from "../../api/auth"
import { isWeChatAuthMode } from "../../api/config"
import {
  bindPhoneNumber,
  getCurrentUserProfile,
  wxUserLogin,
  type CurrentUserProfile
} from "../../api/user"
import {
  applyPlayer,
  getPlayerProfile,
  type PlayerProfile
} from "../../domain/player/api"
import { getPlayerPrincipal } from "../../product/principal"
import { confirmAction, showMessage, showSuccess } from "../../ui/feedback"

export type PhoneNumberEvent = {
  detail: {
    code?: string
    encryptedData?: string
    iv?: string
    errMsg?: string
  }
}

export function useProfileIdentity() {
  const wechatMode = isWeChatAuthMode()
  const loggedIn = ref(!wechatMode)
  const loginBusy = ref(false)
  const phoneBusy = ref(false)
  const nickname = ref(wechatMode ? "微信用户" : "Demo Customer")
  const avatarUrl = ref("")
  const phone = ref("")
  const userId = ref("")
  const role = ref("USER")
  const playerName = ref("")
  const playerProfile = ref<PlayerProfile | null>(null)
  const playerChecked = ref(!wechatMode)
  const applyOpen = ref(false)
  const applyName = ref("")
  const applyBio = ref("")
  const applying = ref(false)

  const phoneText = computed(() => phone.value || "绑定手机号")

  function resetWechatProfile() {
    loggedIn.value = false
    nickname.value = "微信用户"
    avatarUrl.value = ""
    phone.value = ""
    userId.value = ""
    role.value = "USER"
    playerName.value = ""
    playerProfile.value = null
    playerChecked.value = true
    applyOpen.value = false
  }

  function applyUserProfile(profile: CurrentUserProfile) {
    loggedIn.value = true
    userId.value = profile.userId
    nickname.value = profile.nickname || "微信用户"
    avatarUrl.value = profile.avatarUrl || ""
    phone.value = profile.phone || ""
    role.value = profile.role || "USER"
  }

  async function loadPlayerForWechat() {
    if (!userId.value) {
      playerChecked.value = true
      return
    }
    try {
      playerProfile.value = await getPlayerProfile(userId.value)
      playerName.value = playerProfile.value.display_name
    } catch (error) {
      const message = error instanceof Error ? error.message : ""
      if (message !== "PLAYER_PROFILE_NOT_FOUND") throw error
      playerProfile.value = null
      playerName.value = ""
    } finally {
      playerChecked.value = true
    }
  }

  async function loadIdentity(): Promise<void> {
    try {
      if (!wechatMode) {
        loggedIn.value = true
        const player = await getPlayerPrincipal()
        playerName.value = player?.displayName ?? ""
        playerChecked.value = true
        return
      }

      if (!getStoredSession()?.accessToken) {
        resetWechatProfile()
        return
      }

      playerChecked.value = false
      applyUserProfile(await getCurrentUserProfile())
      await loadPlayerForWechat()
    } catch (error) {
      resetWechatProfile()
      showMessage(error instanceof Error ? error.message : "账户加载失败")
    }
  }

  async function loginWithWechat(): Promise<void> {
    if (!wechatMode || loginBusy.value) return
    loginBusy.value = true
    try {
      await wxUserLogin()
      applyUserProfile(await getCurrentUserProfile())
      playerChecked.value = false
      await loadPlayerForWechat()
      showSuccess("微信登录成功")
    } catch (error) {
      showMessage(error instanceof Error ? error.message : "微信登录失败")
    } finally {
      loginBusy.value = false
    }
  }

  async function logout(): Promise<void> {
    if (!wechatMode) return
    const confirmed = await confirmAction({
      title: "退出登录",
      content: "退出后需要重新微信登录才能查看订单和个人资料。",
      confirmText: "退出",
      tone: "danger"
    })
    if (!confirmed) return
    await logoutSession()
    resetWechatProfile()
    showSuccess("已退出登录")
  }

  async function bindPhone(event: PhoneNumberEvent): Promise<void> {
    if (!wechatMode || phoneBusy.value) return
    if (!getStoredSession()?.accessToken) {
      await loginWithWechat()
    }
    if (!getStoredSession()?.accessToken) return

    phoneBusy.value = true
    try {
      const result = await bindPhoneNumber(event.detail)
      phone.value = result.phone
      showSuccess("手机号已绑定")
    } catch (error) {
      showMessage(error instanceof Error ? error.message : "手机号绑定失败")
    } finally {
      phoneBusy.value = false
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
    loggedIn,
    loginBusy,
    phoneBusy,
    nickname,
    avatarUrl,
    phone,
    phoneText,
    userId,
    role,
    playerName,
    playerProfile,
    playerChecked,
    applyOpen,
    applyName,
    applyBio,
    applying,
    loadIdentity,
    loginWithWechat,
    logout,
    bindPhone,
    submitApplication
  }
}
