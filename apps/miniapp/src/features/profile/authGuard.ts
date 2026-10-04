import { getStoredSession } from "../../api/auth"
import { navigation } from "../../platform/navigation"
import { confirmAction } from "../../ui/feedback"

export function hasLoginSession(): boolean {
  const session = getStoredSession()
  return Boolean(session?.accessToken && session.refreshExpiresAt > Date.now())
}

export async function requireLoginPrompt(): Promise<boolean> {
  if (hasLoginSession()) return true
  const confirmed = await confirmAction({
    title: "登录提示",
    content: "需要登录后才能操作，是否立即前往登录？",
    confirmText: "确认",
    cancelText: "取消"
  })
  if (confirmed) navigation.push("/pages/login/index")
  return false
}
