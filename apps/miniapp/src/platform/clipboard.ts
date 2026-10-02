export function setClipboardText(value: string): Promise<void> {
  return new Promise((resolve, reject) => {
    uni.setClipboardData({
      data: value,
      success() {
        resolve()
      },
      fail() {
        reject(new Error("CLIPBOARD_WRITE_FAILED"))
      }
    })
  })
}
