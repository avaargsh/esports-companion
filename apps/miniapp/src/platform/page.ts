export function stopPullDownRefresh(): void {
  uni.stopPullDownRefresh()
}


export function scrollToSelector(
  selector: string,
  duration = 260
): void {
  uni.pageScrollTo({ selector, duration })
}
