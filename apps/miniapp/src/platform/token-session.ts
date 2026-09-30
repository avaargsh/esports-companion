import {
  canRefreshSession,
  createSessionStore,
  createSingleFlight,
  isSessionFresh,
  type ExpiringSession
} from "./session"

export type TokenSession = ExpiringSession & {
  tokenType: string
  accessToken: string
  refreshToken: string
}

export type TokenSessionAdapterConfig<TSession extends TokenSession, TPayload> = {
  storageKey: string
  refreshSkewMs?: number
  validate: (value: unknown) => value is TSession
  login: () => Promise<TPayload>
  refresh: (session: TSession) => Promise<TPayload>
  toSession: (payload: TPayload, now: number) => TSession
}

export function createTokenSessionAdapter<
  TSession extends TokenSession,
  TPayload
>(config: TokenSessionAdapterConfig<TSession, TPayload>) {
  const store = createSessionStore<TSession>(config.storageKey, config.validate)
  const flight = createSingleFlight<TSession>()
  const skewMs = config.refreshSkewMs ?? 30_000

  function persist(payload: TPayload): TSession {
    const session = config.toSession(payload, Date.now())
    store.write(session)
    return session
  }

  async function login(): Promise<TSession> {
    return persist(await config.login())
  }

  async function rotate(current: TSession): Promise<TSession> {
    return persist(await config.refresh(current))
  }

  async function ensure(): Promise<TSession> {
    const current = store.read()
    if (current && isSessionFresh(current, skewMs)) return current

    return flight.run(async () => {
      const latest = store.read()
      if (latest && isSessionFresh(latest, skewMs)) return latest

      if (latest && canRefreshSession(latest)) {
        try {
          return await rotate(latest)
        } catch {
          store.clear()
        }
      }
      return login()
    })
  }

  async function refresh(): Promise<TSession> {
    return flight.run(async () => {
      const current = store.read()
      if (current && canRefreshSession(current)) {
        try {
          return await rotate(current)
        } catch {
          store.clear()
        }
      }
      return login()
    })
  }

  return {
    read: store.read,
    clear: store.clear,
    ensure,
    refresh
  }
}
