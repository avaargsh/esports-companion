export type ExpiringSession = {
  expiresAt: number
  refreshExpiresAt: number
}

export function createSessionStore<T>(
  key: string,
  validate: (value: unknown) => value is T
) {
  return {
    read(): T | null {
      const value = uni.getStorageSync(key)
      return validate(value) ? value : null
    },

    write(value: T) {
      uni.setStorageSync(key, value)
    },

    clear() {
      uni.removeStorageSync(key)
    }
  }
}

export function isSessionFresh(
  session: ExpiringSession,
  skewMs = 0,
  now = Date.now()
): boolean {
  return session.expiresAt > now + skewMs
}

export function canRefreshSession(
  session: ExpiringSession,
  now = Date.now()
): boolean {
  return session.refreshExpiresAt > now
}

export function createSingleFlight<T>() {
  let current: Promise<T> | null = null

  return {
    run(task: () => Promise<T>): Promise<T> {
      if (current) return current

      current = task().finally(() => {
        current = null
      })
      return current
    }
  }
}
