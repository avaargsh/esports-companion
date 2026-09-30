type ConfirmOptions = {
  title: string
  content: string
  confirmText?: string
  cancelText?: string
  confirmColor?: string
}

function messageOf(error: unknown, fallback: string) {
  if (error instanceof Error && error.message) return error.message
  if (typeof error === "string" && error) return error
  return fallback
}

export function showSuccess(title: string) {
  uni.showToast({
    title,
    icon: "success",
    duration: 1600
  })
}

export function showError(error: unknown, fallback = "操作失败，请稍后重试") {
  uni.showToast({
    title: messageOf(error, fallback),
    icon: "none",
    duration: 2400
  })
}

export function confirmAction(options: ConfirmOptions): Promise<boolean> {
  return new Promise(resolve => {
    uni.showModal({
      title: options.title,
      content: options.content,
      confirmText: options.confirmText ?? "确认",
      cancelText: options.cancelText ?? "取消",
      confirmColor: options.confirmColor ?? "#6757e6",
      success: result => resolve(result.confirm),
      fail: () => resolve(false)
    })
  })
}

export async function withLoading<T>(
  title: string,
  task: () => Promise<T>
): Promise<T> {
  uni.showLoading({ title, mask: true })
  try {
    return await task()
  } finally {
    uni.hideLoading()
  }
}
