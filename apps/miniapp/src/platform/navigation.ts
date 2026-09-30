export type RouteQueryValue =
  | string
  | number
  | boolean
  | null
  | undefined

export type RouteQuery = Record<string, RouteQueryValue>

export function buildRoute(path: string, query: RouteQuery = {}): string {
  const pairs = Object.entries(query)
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(
      ([key, value]) =>
        `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`
    )

  return pairs.length ? `${path}?${pairs.join("&")}` : path
}

export const navigation = {
  push(path: string, query?: RouteQuery) {
    uni.navigateTo({ url: buildRoute(path, query) })
  },

  replace(path: string, query?: RouteQuery) {
    uni.redirectTo({ url: buildRoute(path, query) })
  },

  tab(path: string) {
    uni.switchTab({ url: path })
  },

  back(delta = 1) {
    uni.navigateBack({ delta })
  }
}
